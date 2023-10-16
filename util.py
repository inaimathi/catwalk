import glob
import os
import re
import subprocess
import tempfile


def fresh_file(prefix, suffix, dir="static"):
    fid, fname= tempfile.mkstemp(prefix=prefix, suffix=suffix, dir=dir)
    os.close(fid)
    return fname

def _silence_location_pairs(audio_file):
    cmd = ["ffmpeg", "-i", audio_file, "-af", "silencedetect=n=-50dB:d=1", "-f", "null", "-"]
    res = subprocess.run(cmd, check=True, stderr=subprocess.PIPE)
    lines = res.stderr.decode("utf-8").splitlines()
    filtered = (ln for ln in lines if ln.startswith("[silencedetect"))
    subbed = [
        re.sub("^\[.*?\] ", "", ln)
        for ln in filtered
    ]
    pairs = (subbed[i:i+2] for i in range(0, len(subbed), 2))
    for (start, end) in pairs:
        yield start.split(": ")[1].strip()
        yield end.split(" | ")[0].split(": ")[1].strip()

def split_audio_by_silence(audio_file):
    name, ext = os.path.splitext(os.path.basename(audio_file))
    pairs = _silence_location_pairs(audio_file)
    subprocess.run(["ffmpeg", "-i", audio_file, "-f", "segment", "-segment_times", ",".join(list(pairs)) , "-reset_timestamps", "1", "-map", "0:a", "-c:a", "copy", f"{name}-part-%03d{ext}"])
    return sorted(glob.glob(f"{name}-part-*{ext}"))
