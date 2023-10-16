import os
import tempfile


def fresh_file(prefix, suffix, dir="static"):
    fid, fname= tempfile.mkstemp(prefix=f"audio-{voice}-", suffix=".wav", dir="static")
    os.close(fid)
    return fname
