import os
import tempfile

import torchaudio
from tortoise.api import TextToSpeech
from tortoise.utils.audio import load_voices

_TTS = TextToSpeech(kv_cache=True, half=True, use_deepspeed=True)
_VOICES = {"leo": load_voices(["leo"], extra_voice_dirs=["extra-voices"])}

def _save(arr, voice):
    fid, fname= tempfile.mkstemp(prefix=f"audio-{voice}-", suffix=".wav", dir="static")
    os.close(fid)
    torchaudio.save(fname, arr.squeeze(0).cpu(), 24000)
    return fname

def text_to_wavs(text, voice=None, k=3):
    assert (10 >= k >= 1), f"k must be between 1 and 10. got {k}"
    if voice is None:
        voice = "leo"
    samples, latents = _VOICES[voice]
    gen = _TTS.tts_with_preset(text, k=k, voice_samples=samples)
    if isinstance(gen, list):
        return [_save(g, voice) for g in gen]
    return [_save(gen, voice)]
