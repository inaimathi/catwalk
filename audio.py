import os
import subprocess

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
    outfile = util.fresh_file("blogcast", ".wav")
    subprocess.call(["sox", *fnames, outfile])
    return outfile
