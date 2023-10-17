import os

import torchaudio
from tortoise.api import TextToSpeech
from tortoise.utils.audio import get_voices, load_voices

import util

_TTS = TextToSpeech(kv_cache=True, half=True, use_deepspeed=True)
_VOICES = {
    voice: load_voices([voice], extra_voice_dirs=["extra-voices"])
    for voice in get_voices(["extra-voices"])
}

def get_voices():
    return sorted(_VOICES.keys())

def _save(arr, voice):
    fname = util.fresh_file(f"audio-{voice}-", ".wav")
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
