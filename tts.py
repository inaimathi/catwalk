from scipy.io.wavfile import write
from transformers import AutoProcessor, BarkModel

_PROCESSOR = AutoProcessor.from_pretrained("suno/bark")
_MODEL = BarkModel.from_pretrained("suno/bark")

def text_to_wav(filename, text, voice=None):
    if voice is None:
        voice = "v2/en_speaker_6"
    inputs = _PROCESSOR(text, voice_preset=voice)
    audio_array = _MODEL.generate(**inputs)
    write(
        filename,
        _MODEL.generation_config.sample_rate,
        audio_array.cpu().numpy().squeeze()
    )
    return filename
