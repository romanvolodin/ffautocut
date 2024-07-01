import json
import subprocess

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


if __name__ == "__main__":
    selected_strips = filter_selected_strips(bpy.context)

    for strip in selected_strips:
        strip_timeline_offset = strip.frame_final_start

        out = detect_cuts_with_ffprobe(
            ffprobe="ffprobe",
            filepath=strip.filepath,
            time_start=0,
            time_end=49,
            threshold=0.1
        )

        for cut in out['frames']:
            time_in_seconds = float(cut['pkt_dts_time'])
            time_in_frames = round(time_in_seconds * strip.fps) + strip_timeline_offset
            print(time_in_seconds, time_in_frames)