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


def detect_cuts_with_ffprobe(ffprobe, filepath, time_start, time_end, threshold=0.1):
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
    detect_cuts_threshold,
):
    NAME = "PRM_SHOT"
    RED = "COLOR_01"

    se = context.scene.sequence_editor
    strip = se.sequences.new_movie(NAME, filepath, channel, frame_start)
    strip.frame_offset_start = frame_offset_start
    strip.frame_offset_end = frame_offset_end
    strip.frame_final_duration = frame_final_duration
    strip.color_tag = RED
    strip.detect_cuts_threshold = detect_cuts_threshold
    return strip


def combine_strips(context, strips):
    if not strips or len(strips) == 1:
        return

    sorted_strips = sorted(strips, key=lambda strip: strip.frame_final_start)
    first_strip, *rest_strips = sorted_strips

    for next_strip in rest_strips.copy():
        if (
            first_strip.filepath != next_strip.filepath
            or first_strip.frame_final_end != next_strip.frame_final_start
            or first_strip.frame_start != next_strip.frame_start
        ):
            combine_strips(context, rest_strips)
            return

        next_strip_end = next_strip.frame_final_end
        rest_strips.pop(rest_strips.index(next_strip))
        context.scene.sequence_editor.sequences.remove(next_strip)
        first_strip.frame_final_end = next_strip_end


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


def main(context, ffprobe, threshold):
    selected_strips = filter_selected_strips(context)

    for strip in selected_strips:
        strip_start_in_seconds = strip.frame_final_start / strip.fps
        strip_end_in_seconds = strip.frame_final_end / strip.fps
        video_filepath = abspath(strip.filepath)

        out = detect_cuts_with_ffprobe(
            ffprobe=ffprobe,
            filepath=video_filepath,
            time_start=strip_start_in_seconds,
            time_end=strip_end_in_seconds,
            threshold=threshold,
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

            if start < strip.frame_final_start or end > strip.frame_final_end:
                continue

            added_strip = add_strip(
                context,
                video_filepath,
                frame_start=int(strip.frame_start),
                frame_offset_start=start,
                frame_offset_end=end,
                frame_final_duration=end - start,
                channel=strip.channel + 1,
                detect_cuts_threshold=threshold,
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

    threshold: bpy.props.FloatProperty(default=0.1)

    def execute(self, context):
        preferences = context.preferences.addons[__name__].preferences
        main(bpy.context, preferences.ffprobe, self.threshold)
        return {"FINISHED"}


class CombineStrips(Operator):
    bl_idname = "sequence.combine_strips"
    bl_label = "Combine Strips"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        selected_strips = filter_selected_strips(context)
        combine_strips(context, selected_strips)
        return {"FINISHED"}


class SEQUENCE_PT_detect_cut(Panel):
    bl_label = "FFAutoCut {}.{}.{}".format(*bl_info["version"])
    bl_category = "FFAutoCut"
    bl_space_type = "SEQUENCE_EDITOR"
    bl_region_type = "UI"

    def draw(self, context):
        selected_strips = filter_selected_strips(context)

        layout = self.layout
        col = layout.column(align=True)

        if not selected_strips:
            col.label(text="No strips selected")
            return

        col.prop(selected_strips[0], "detect_cuts_threshold", text="Threshold")

        row = layout.row(align=True)
        row.scale_y = 1.5
        operator = row.operator("sequence.detect_cut", text="Detect cuts")
        operator.threshold = selected_strips[0].detect_cuts_threshold
        layout.label(text="")
        layout.operator("sequence.combine_strips")


addon_keymaps = []


def register():
    bpy.utils.register_class(FFAutoCut)
    bpy.utils.register_class(CombineStrips)
    bpy.utils.register_class(Preferences)
    bpy.utils.register_class(SEQUENCE_PT_detect_cut)

    bpy.types.MovieSequence.detect_cuts_threshold = bpy.props.FloatProperty(
        default=0.1,
        soft_max=1.0,
        soft_min=0.01,
    )

    window_manager = bpy.context.window_manager
    keyconfig = window_manager.keyconfigs.addon
    if keyconfig:
        keymap = keyconfig.keymaps.new(name="SequencerCommon", space_type="SEQUENCE_EDITOR")
        keymap_item = keymap.keymap_items.new("sequence.combine_strips", type="J", value="PRESS")
        addon_keymaps.append((keymap, keymap_item))


def unregister():
    bpy.utils.unregister_class(FFAutoCut)
    bpy.utils.unregister_class(CombineStrips)
    bpy.utils.unregister_class(Preferences)
    bpy.utils.unregister_class(SEQUENCE_PT_detect_cut)

    del bpy.types.MovieSequence.detect_cuts_threshold

    for keymap, keymap_item in addon_keymaps:
        keymap.keymap_items.remove(keymap_item)
    addon_keymaps.clear()


if __name__ == "__main__":
    register()
