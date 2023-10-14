import os
import tempfile

import torchaudio
from tortoise.api import TextToSpeech
from tortoise.utils.audio import load_voices

# from transformers import AutoProcessor, BarkModel

# _DEV = "cuda" # "cpu"
# _PROCESSOR = AutoProcessor.from_pretrained("suno/bark")
# _MODEL = BarkModel.from_pretrained("suno/bark").to(_DEV).to_bettertransformer()
# _MODEL.enable_cpu_offload()

_TTS = TextToSpeech()
_VOICES = {"leo": load_voices(["leo"], extra_voice_dirs=["extra-voices"])}

# def text_to_wav(filename, text, voice=None):
#     if voice is None:
#         voice = "v2/en_speaker_6"
#     inputs = _PROCESSOR(text, voice_preset=voice).to(_DEV)
#     audio_array = _MODEL.generate(**inputs)
#     write(
#         filename,
#         _MODEL.generation_config.sample_rate,
#         audio_array.cpu().numpy().squeeze()
#     )
#     return filename

def _save(arr, voice):
    fid, fname= tempfile.mkstemp(prefix=f"audio-{voice}-", suffix=".wav", dir="static")
    os.close(fid)
    torchaudio.save(fname, arr.squeeze(0).cpu(), 24000)
    return fname


def text_to_wavs(text, voice=None, k=3):
    assert (10 >= k >= 1), "k must be between 1 and 10"
    if voice is None:
        voice = "leo"
    samples, latents = _VOICES[voice]
    gen = _TTS.tts_with_preset(text, k=k, voice_samples=samples)
    if isinstance(gen, list):
        return [_save(g, voice) for g in gen]
    return [_save(gen, voice)]
