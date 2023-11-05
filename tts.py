import os
import string

import editdistance
import torchaudio
from tortoise.api import TextToSpeech
from tortoise.utils.audio import get_voices, load_voices

import basics
import util

print("Loading TTS...")
_TTS = TextToSpeech(kv_cache=True, half=True, use_deepspeed=True, device=util.dev_by(name="1080"))
_VOICES = {
    voice: load_voices([voice], extra_voice_dirs=["extra-voices"])
    for voice in get_voices(["extra-voices"])
}

def _clean(s):
    return s.lower().translate(str.maketrans('', '', string.punctuation))

def _dist(a, b):
    return editdistance.distance(_clean(a), _clean(b))

def _thresh(fname, original):
    numer = _dist(original, basics.transcribe(fname))
    denom = float(len(_clean(original)))
    if denom == 0.0:
        if numer == 0.0:
            return 0.0
        return 1.0
    return  numer / denom

def get_voices():
    return sorted(_VOICES.keys())

def _save(arr, voice):
    fname = util.fresh_file(f"audio-{voice}-", ".wav")
    torchaudio.save(fname, arr.squeeze(0).cpu(), 24000)
    return fname

def text_to_wavs(text, voice=None, k=3, threshold=0.1, max_tries=3):
    assert (10 >= k >= 1), f"k must be between 1 and 10. got {k}"
    if voice is None:
        voice = "leo"
    samples, latents = _VOICES[voice]
    candidates = []
    tries = 0
    while True:
        tries += 1
        with util.silence():
            gen = _TTS.tts_with_preset(text, k=k, voice_samples=samples)
        if isinstance(gen, list):
            fs = [_save(g, voice) for g in gen]
        else:
            fs = [_save(gen, voice)]
        candidates += [(f, _thresh(f, text)) for f in fs]
        candidates.sort(key=lambda el: el[1])
        if tries >= max_tries:
            break
        if len([f for f, dif in candidates if dif < threshold]) >= k:
            break

    return [f for f, _ in candidates[:k]]
