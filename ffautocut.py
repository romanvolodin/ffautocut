import json
import subprocess
from itertools import chain, pairwise

import bpy


def filter_selected_strips(context, types=('MOVIE',)):
    selected_strips = [
        strip for strip in context.selected_sequences if strip.type in types
    ]
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


def generate_cut_pairs(ffrobe_output, duration, fps):
    cuts_in_seconds = [float(frame["pkt_dts_time"]) for frame in ffrobe_output["frames"]]
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


if __name__ == "__main__":
    selected_strips = filter_selected_strips(bpy.context)

    for strip in selected_strips:
        strip_timeline_offset = strip.frame_final_start
        strip_duration_in_seconds = strip.frame_duration / strip.fps

        out = detect_cuts_with_ffprobe(
            ffprobe="ffprobe",
            filepath=strip.filepath,
            time_start=0,
            time_end=strip_duration_in_seconds,
            threshold=0.1
        )

        cut_pairs = list(generate_cut_pairs(
            out,
            strip.frame_duration,
            strip.fps,
        ))

        for pair in cut_pairs:
            start, end = pair

            added_strip = add_strip(
                bpy.context,
                strip.filepath,
                frame_start=strip_timeline_offset,
                frame_offset_start=start,
                frame_offset_end=end,
                frame_final_duration=end - start,
                channel=strip.channel + 1
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