import string
import tempfile

import editdistance
import torchaudio
import tortoise.utils.audio as audio
from tortoise.api import TextToSpeech

import audio as autil
import basics
import util

print("Loading TTS...")
_TTS = None
_VOICES = {}


def init_voices():
    global _VOICES
    if not _VOICES:
        _VOICES = {
            voice: audio.load_voices([voice], extra_voice_dirs=["extra-voices"])
            for voice in audio.get_voices(["extra-voices"])
        }


def init():
    global _TTS
    if _TTS is None:
        _TTS = TextToSpeech(kv_cache=True, half=True)
    init_voices()


def _clean(s):
    return s.lower().translate(str.maketrans("", "", string.punctuation))


def get_voices():
    init_voices()
    return sorted(_VOICES.keys())


def _save(arr, voice):
    fname = util.fresh_file(f"audio-{voice}-", ".wav")
    torchaudio.save(fname, arr.squeeze(0).cpu(), 24000)
    return fname


def _estimate_duration(text):
    with tempfile.NamedTemporaryFile() as tmp:
        util.silent_cmd(["espeak", "-w", tmp.name, text])
        return autil.duration_of(tmp.name)


def _duration_distance(fname, estimated):
    return abs(estimated - (autil.duration_of(fname)))


def _transcript_distance(fname, original):
    return editdistance.distance(_clean(original), _clean(basics.transcribe(fname)))


def text_to_wavs(text, voice=None, k=3):
    init()
    assert 10 >= k >= 1, f"k must be between 1 and 10. got {k}"
    if voice is None:
        voice = "leo"
    samples, latents = _VOICES[voice]
    estimated_duration = _estimate_duration(text)
    with util.silence():
        gen = _TTS.tts_with_preset(text, k=k, voice_samples=samples)
    if isinstance(gen, list):
        fs = [_save(g, voice) for g in gen]
    else:
        fs = [_save(gen, voice)]
    candidates = sorted(
        [
            (
                _transcript_distance(f, text),
                _duration_distance(f, estimated_duration),
                f,
            )
            for f in fs
        ]
    )

    return [f for _, _, f in candidates[:k]]
