import contextlib
import glob
import io
import itertools
import os
import re
import subprocess
import sys
import tempfile

import torch
import tqdm

FF_HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:109.0) Gecko/20100101 Firefox/119.0",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "en-CA,en-US;q=0.7,en;q=0.3",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "cross-site",
}


@contextlib.contextmanager
def silence():
    saved_out = sys.stdout
    saved_err = sys.stderr
    sys.stdout = io.StringIO()
    sys.stderr = io.StringIO()
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


def feh(fname_or_list):
    cmd = ["feh", "-Fs"]
    if isinstance(fname_or_list, str):
        fname_or_list = [fname_or_list]
    silent_cmd(cmd + fname_or_list)


def fehgrid(w, h, flist):
    imgW = 200
    cmd = [
        "feh",
        "-Fsi",
        "--index-info",
        "''",
        "--thumb-width",
        str(imgW),
        "--thumb-height",
        str(imgW),
        "--limit-width",
        str(w * imgW),
        "--limit-height",
        str((h + 1) * imgW),
    ]
    silent_cmd(cmd + flist)


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
    res = subprocess.check_output(["sox", "--i", audio_fname])
    splits = (re.split(" *: +", ln) for ln in res.decode("utf-8").splitlines() if ln)
    return {k.lower().replace(" ", "-"): v for k, v in splits}


def batched(iterable, n):
    # batched('ABCDEFG', 3) --> ABC DEF G
    if n < 1:
        raise ValueError("n must be at least one")
    it = iter(iterable)
    while batch := tuple(itertools.islice(it, n)):
        yield batch


def fresh_file(prefix, suffix, dir="static"):
    fid, fname = tempfile.mkstemp(prefix=prefix, suffix=suffix, dir=dir)
    os.close(fid)
    return fname


def force_static(fname):
    return os.path.join("/static/", os.path.basename(fname))


def _silence_locations(audio_file, silence_duration, dB_threshold):
    cmd = [
        "ffmpeg",
        "-i",
        audio_file,
        "-af",
        f"silencedetect=n={dB_threshold}dB:d={silence_duration}",
        "-f",
        "null",
        "-",
    ]
    res = subprocess.run(cmd, check=True, stderr=subprocess.PIPE)
    lines = res.stderr.decode("utf-8").splitlines()
    filtered = (ln for ln in lines if ln.startswith("[silencedetect"))
    subbed = [re.sub("^\[.*?\] ", "", ln) for ln in filtered]
    pairs = (subbed[i : i + 2] for i in range(0, len(subbed), 2))
    for start, end in pairs:
        yield start.split(": ")[1].strip()
        yield end.split(" | ")[0].split(": ")[1].strip()


def split_audio_by_silence(audio_file, silence_duration=1, dB_threshold=-50):
    name, ext = os.path.splitext(os.path.basename(audio_file))
    thresh = dB_threshold
    silence_locs = []
    print("Figuring out silence locs...")
    while not silence_locs:
        silence_locs = list(_silence_locations(audio_file, silence_duration, thresh))
        print(f"    {len(silence_locs)}")
        thresh += 5
    first_silence_start = silence_locs[0]
    print(f"  processing first silence 0-{first_silence_start}...")
    silent_cmd(
        [
            "ffmpeg",
            "-i",
            audio_file,
            "-to",
            first_silence_start,
            "-c",
            "copy",
            f"{name}-part-00000{ext}",
        ]
    )
    print("  processing remainder...")
    end_start_pairs = list(batched(silence_locs[1:], 2))[:-1]
    pbar = tqdm.tqdm(total=len(end_start_pairs), ascii=True)
    for ix, (end, start) in enumerate(end_start_pairs, start=1):
        pbar.update(1)
        silent_cmd(
            [
                "ffmpeg",
                "-i",
                audio_file,
                "-ss",
                end,
                "-to",
                start,
                "-c",
                "copy",
                f"{name}-part-{str(ix).zfill(5)}{ext}",
            ]
        )
    #        subprocess.run(["ffmpeg", "-i", audio_file, "-f", "segment", "-segment_times", ",".join(list(pairs)) , "-reset_timestamps", "1", "-map", "0:a", "-c:a", "copy", f"{name}-part-%03d{ext}"])
    return sorted(glob.glob(f"{name}-part-*{ext}"))


def youtube_audio(output, url):
    subprocess.call(
        ["youtube-dl", "-o", f"{output}.%(ext)s", "-x", "--audio-format", "wav", url]
    )
    return glob.glob(f"{output}.wav")[0]


def splits_from_url(output, url):
    return split_audio_by_silence(youtube_audio(output, url), dB_threshold=-50)


def gpu_props(ix):
    props = torch.cuda.get_device_properties(ix)
    mem = torch.cuda.mem_get_info(ix)
    return {
        "ix": ix,
        "name": props.name,
        "cores": props.multi_processor_count,
        "mem_free": mem[0] / 1000000,
        "mem_total": mem[1] / 1000000,
    }


def list_gpus():
    return [gpu_props(ix) for ix in range(torch.cuda.device_count())]


def gpu_ix_by_substring(substr):
    for dev in list_gpus():
        if substr in dev["name"]:
            return dev["ix"]


def dev_by(name=None, ix=None):
    if ix is not None:
        # Use given ix
        dev_ix = ix
    elif name is not None:
        # Find a GPU by given substring
        dev_ix = gpu_ix_by_substring(name)
    else:
        # Find GPU with most remaining free memory
        dev_ix = sorted(list_gpus(), key=lambda d: d["mem_free"], reverse=True)[0]["ix"]
    if dev_ix is not None:
        return f"cuda:{dev_ix}"


def to_gpu(torch_thing, name=None, ix=None):
    dev = dev_by(name=name, ix=ix)
    if dev is not None:
        torch_thing.to(dev)
    return torch_thing
