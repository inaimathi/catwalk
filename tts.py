import torch
from scipy.io.wavfile import write
from transformers import AutoProcessor, BarkModel

_DEV = "cuda" # "cpu"
_PROCESSOR = AutoProcessor.from_pretrained("suno/bark", torch_dtype=torch.float16)
_MODEL = BarkModel.from_pretrained("suno/bark", torch_dtype=torch.float16).to(_DEV).to_bettertransformer()
_MODEL.enable_cpu_offload()

def text_to_wav(filename, text, voice=None):
    if voice is None:
        voice = "v2/en_speaker_6"
    inputs = _PROCESSOR(text, voice_preset=voice).to(_DEV)
    audio_array = _MODEL.generate(**inputs)
    write(
        filename,
        _MODEL.generation_config.sample_rate,
        audio_array.cpu().numpy().squeeze()
    )
    return filename
