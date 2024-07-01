import json
import subprocess


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
    out = detect_cuts_with_ffprobe(
        ffprobe="ffprobe",
        filepath="test_clip.mov",
        time_start=0,
        time_end=49,
        threshold=0.1
    )

    for cut in out['frames']:
        time = float(cut['pkt_dts_time'])
        print(time, time*24, round(time*24))