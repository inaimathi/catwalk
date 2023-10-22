import contextlib
import glob
import io
import itertools
import os
import re
import subprocess
import sys
import tempfile


@contextlib.contextmanager
def silence():
    saved_out = sys.stdout
    saved_err = sys.stderr
    sys.stdout = None
    sys.stderr = None
    try:
        yield
    finally:
        sys.stdout = saved_out
        sys.stderr = saved_err

def play(fname_or_list):
    if isinstance(fname_or_list, list):
        for el in fname_or_list:
            subprocess.check_output(["mplayer", el])
        return
    subprocess.check_output(["mplayer", fname_or_list])

def audio_info(audio_fname):
    res = check_output(["sox", "--i", sound_fname])
    splits = (re.split(" *: +", ln) for ln in res.decode("utf-8").splitlines() if ln)
    return {k.lower().replace(' ', '-'): v for k, v in splits}

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

def _silence_locations(audio_file, silence_duration, dB_threshold):
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

def split_audio_by_silence(audio_file, silence_duration=1, dB_threshold=-50):
    name, ext = os.path.splitext(os.path.basename(audio_file))
    silence_locs = _silence_locations(audio_file, silence_duration, dB_threshold)
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
