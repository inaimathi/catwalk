import datetime
import os
import subprocess

import srt

import util


def duration_of(fname):
    "Returns the duration of the given audio file in seconds"
    cmd = [
        "ffprobe",
        "-show_entries",
        "format=duration",
        "-of",
        "default=noprint_wrappers=1:nokey=1",
        fname,
    ]
    return float(util.silent_cmd(cmd))


def silence(duration, rate=24000, channels=1):
    fname = f"silence-{duration}.wav"
    if not os.path.exists(fname):
        subprocess.call(
            [
                "sox",
                "-n",
                "-r",
                str(rate),
                "-c",
                str(channels),
                fname,
                "trim",
                "0.0",
                str(duration),
            ]
        )
    return fname


def stitch(files_and_silences_list):
    fnames = [
        f if type(f) is str else silence(f["silence"]) for f in files_and_silences_list
    ]
    outfile = util.fresh_file("stitched", ".wav")
    subprocess.call(["sox", *fnames, outfile])
    return outfile


def _tsec(secs):
    return srt.timedelta_to_srt_timestamp(datetime.timedelta(seconds=secs)).replace(
        ",", "."
    )


def slice(fname, start, end):
    outf = util.fresh_file("audio-slice", os.path.splitext(fname)[1])
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-i",
            fname,
            "-ss",
            _tsec(start),
            "-t",
            _tsec(end),
            outf,
        ],
        stderr=subprocess.DEVNULL,
    )
    return outf
