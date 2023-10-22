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
    sys.stdout = io.BytesIO()
    sys.stderr = io.BytesIO()
    try:
        yield
    finally:
        sys.stdout.close()
        sys.stderr.close()
        sys.stdout = saved_out
        sys.stderr = saved_err

@contextlib.contextmanager
def key_interrupt():
    try:
        yield
    except KeyboardInterrupt:
        print("\nInterrupted...\n")

def silent_cmd(command):
    return subprocess.check_output(command, stderr=subprocess.DEVNULL)

def play(fname_or_list):
    with key_interrupt():
        if isinstance(fname_or_list, list):
            for el in fname_or_list:
                print(el)
                with silence():
                    silent_cmd(["mplayer", el])
            return fname_or_list
        with silence():
            silent_cmd(["mplayer", fname_or_list])
        return fname_or_list

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
    silent_cmd([
        "ffmpeg", "-i", audio_file,
        "-to", first_silence_start, "-c", "copy",
        f"{name}-part-00000{ext}"
    ])
    end_start_pairs = list(batched(silence_locs, 2))[:-1]
    for ix, (end, start) in enumerate(end_start_pairs):
        silent_cmd([
            "ffmpeg", "-i", audio_file,
            "-ss", end, "-to", start, "-c", "copy",
            f"{name}-part-{str(ix).zfill(5)}{ext}"
        ])
#        subprocess.run(["ffmpeg", "-i", audio_file, "-f", "segment", "-segment_times", ",".join(list(pairs)) , "-reset_timestamps", "1", "-map", "0:a", "-c:a", "copy", f"{name}-part-%03d{ext}"])
    return sorted(glob.glob(f"{name}-part-*{ext}"))
