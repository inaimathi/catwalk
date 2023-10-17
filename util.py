import glob
import itertools
import os
import re
import subprocess
import tempfile


def play(fname):
    subprocess.check_output(["mplayer", fname])

def batched(iterable, n):
    # batched('ABCDEFG', 3) --> ABC DEF G
    if n < 1:
        raise ValueError('n must be at least one')
    it = iter(iterable)
    while batch := tuple(itertools.islice(it, n)):
        yield batch

def fresh_file(prefix, suffix, dir="static"):
    fid, fname= tempfile.mkstemp(prefix=prefix, suffix=suffix, dir=dir)
    os.close(fid)
    return fname

def _silence_locations(audio_file, silence_duration=1, dB_threshold = -50):
    cmd = [
        "ffmpeg", "-i", audio_file, "-af",
        f"silencedetect=n={dB_threshold}dB:d={silence_duration}",
        "-f", "null", "-"
    ]
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
    silence_locs = _silence_locations(audio_file)
    first_silence_start = next(silence_locs)
    subprocess.run([
        "ffmpeg", "-i", audio_file,
        "-to", first_silence_start, "-c", "copy",
        f"{name}-part-00000{ext}"
    ], stderr=subprocess.DEVNULL)
    end_start_pairs = list(batched(silence_locs, 2))[:-1]
    for ix, (end, start) in enumerate(end_start_pairs):
        subprocess.run([
            "ffmpeg", "-i", audio_file,
            "-ss", end, "-to", start, "-c", "copy",
            f"{name}-part-{str(ix).zfill(5)}{ext}"
        ], stderr=subprocess.DEVNULL)
#        subprocess.run(["ffmpeg", "-i", audio_file, "-f", "segment", "-segment_times", ",".join(list(pairs)) , "-reset_timestamps", "1", "-map", "0:a", "-c:a", "copy", f"{name}-part-%03d{ext}"])
    return sorted(glob.glob(f"{name}-part-*{ext}"))
