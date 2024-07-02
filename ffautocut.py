import json
import subprocess
from itertools import chain, pairwise

import bpy
from bpy.path import abspath
from bpy.props import StringProperty
from bpy.types import AddonPreferences, Operator, Panel


bl_info = {
    "name": "FFAutoCut",
    "author": "Roman Volodin",
    "version": (1, 0, 0),
    "blender": (3, 0, 0),
    "location": "Sequence Editor -> N-panel",
    "description": "Automatic scene cut detection with FFprobe",
    "warning": "",
    "doc_url": "",
    "tracker_url": "",
    "category": "Sequencer",
}


def filter_selected_strips(context, types=("MOVIE",)):
    selected_strips = [strip for strip in context.selected_sequences if strip.type in types]
    if selected_strips:
        return selected_strips


def detect_cuts_with_ffprobe(ffprobe, filepath, time_start, time_end, threshold=0.3):
    output = subprocess.check_output(
        (
            f"{ffprobe} -hide_banner -show_frames -print_format json -f lavfi "
            f"'movie={filepath}:seek_point={time_start},trim={time_start}:{time_end},select=gt(scene\,{threshold})'"
        ),
        shell=True,
    )
    return json.loads(output.decode("utf-8"))


def generate_cut_pairs(ffprobe_output, duration, fps):
    cuts_in_seconds = [float(frame["pkt_dts_time"]) for frame in ffprobe_output["frames"]]
    cuts_in_frames = [round(time * fps) for time in cuts_in_seconds]
    pairs = pairwise(chain.from_iterable(([0], cuts_in_frames, [duration])))
    return pairs


def add_strip(
    context,
    filepath,
    frame_start,
    frame_offset_start,
    frame_offset_end,
    frame_final_duration,
    channel,
):
    NAME = "PRM_SHOT"
    RED = "COLOR_01"

    se = context.scene.sequence_editor
    strip = se.sequences.new_movie(NAME, filepath, channel, frame_start)
    strip.frame_offset_start = frame_offset_start
    strip.frame_offset_end = frame_offset_end
    strip.frame_final_duration = frame_final_duration
    strip.color_tag = RED
    return strip


def combine_strips(context, strip1, strip2):
    if strip1.filepath != strip2.filepath:
        return

    if strip1.frame_final_end != strip2.frame_final_start:
        return

    if strip1.frame_start != strip2.frame_start:
        return

    strip2_end = strip2.frame_final_end
    context.scene.sequence_editor.sequences.remove(strip2)
    strip1.frame_final_end = strip2_end


def print_strip_info(strip):
    print(f"{strip.name=}")
    print(f"{strip.fps=}")
    print(f"{strip.frame_duration=}")
    print(f"{strip.frame_final_duration=}")
    print(f"{strip.frame_final_end=}")
    print(f"{strip.frame_final_start=}")
    print(f"{strip.frame_offset_end=}")
    print(f"{strip.frame_offset_start=}")
    print(f"{strip.frame_start=}")
    print()


def main(context, ffprobe):
    selected_strips = filter_selected_strips(context)

    for strip in selected_strips:
        strip_timeline_offset = strip.frame_final_start
        strip_duration_in_seconds = strip.frame_duration / strip.fps
        video_filepath = abspath(strip.filepath)

        out = detect_cuts_with_ffprobe(
            ffprobe=ffprobe,
            filepath=video_filepath,
            time_start=0,
            time_end=strip_duration_in_seconds,
            threshold=0.1,
        )

        cut_pairs = list(
            generate_cut_pairs(
                out,
                strip.frame_duration,
                strip.fps,
            )
        )

        for pair in cut_pairs:
            start, end = pair

            added_strip = add_strip(
                context,
                video_filepath,
                frame_start=strip_timeline_offset,
                frame_offset_start=start,
                frame_offset_end=end,
                frame_final_duration=end - start,
                channel=strip.channel + 1,
            )
            added_strip.transform.filter = strip.transform.filter
            added_strip.transform.scale_x = strip.transform.scale_x
            added_strip.transform.scale_y = strip.transform.scale_y
            added_strip.transform.rotation = strip.transform.rotation
            added_strip.transform.offset_x = strip.transform.offset_x
            added_strip.transform.offset_y = strip.transform.offset_y
            added_strip.transform.origin = strip.transform.origin
            added_strip.use_flip_x = strip.use_flip_x
            added_strip.use_flip_y = strip.use_flip_y


class Preferences(AddonPreferences):
    bl_idname = __name__

    ffprobe: StringProperty(
        name="ffprobe",
        subtype="FILE_PATH",
        description="Command or path to run ffprobe",
        default="ffprobe",
    )

    def draw(self, context):
        layout = self.layout
        layout.prop(self, "ffprobe")


class FFAutoCut(Operator):
    bl_idname = "sequence.detect_cut"
    bl_label = "FFAutoCut"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        preferences = context.preferences.addons[__name__].preferences
        main(bpy.context, preferences.ffprobe)
        return {"FINISHED"}


class CombineStrips(Operator):
    bl_idname = "sequence.combine_strips"
    bl_label = "Combine Strips"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        selected_strips = filter_selected_strips(context)
        strip1, strip2 = selected_strips
        combine_strips(context, strip1, strip2)
        return {"FINISHED"}


class SEQUENCE_PT_detect_cut(Panel):
    bl_label = "FFAutoCut {}.{}.{}".format(*bl_info["version"])
    bl_category = "FFAutoCut"
    bl_space_type = "SEQUENCE_EDITOR"
    bl_region_type = "UI"

    def draw(self, context):
        layout = self.layout
        row = layout.row(align=True)
        row.scale_y = 1.5
        row.operator("sequence.detect_cut", text="Detect cuts")
        layout.operator("sequence.combine_strips")


def register():
    bpy.utils.register_class(FFAutoCut)
    bpy.utils.register_class(CombineStrips)
    bpy.utils.register_class(Preferences)
    bpy.utils.register_class(SEQUENCE_PT_detect_cut)


def unregister():
    bpy.utils.unregister_class(FFAutoCut)
    bpy.utils.unregister_class(CombineStrips)
    bpy.utils.unregister_class(Preferences)
    bpy.utils.unregister_class(SEQUENCE_PT_detect_cut)


if __name__ == "__main__":
    register()
