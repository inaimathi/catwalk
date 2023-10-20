import torch
import transformers
import whisper
from transformers import AutoModelForCausalLM, AutoTokenizer, pipeline

_WHISPER = whisper.load_model("base")

def transcribe(audio_file):
    audio = whisper.load_audio(audio_file)
    audio = whisper.pad_or_trim(audio)
    mel = whisper.log_mel_spectrogram(audio).to(_WHISPER.device)

    _, probs = _WHISPER.detect_language(mel)
    opts = whisper.DecodingOptions()

    result = whisper.decode(_WHISPER, mel, opts)

    return result.text



#_CAPTIONER = pipeline("image-to-text", model="Salesforce/blip-image-captioning-base")
_CAPTIONER = pipeline("image-to-text", model="Salesforce/blip2-flan-t5-xl")

def caption_image(url):
    return _CAPTIONER(url)

_TEXT_MODEL = "tiiuae/falcon-7b-instruct"
_TOKENIZER = AutoTokenizer.from_pretrained(_TEXT_MODEL)
# _PIPE = transformers.pipeline(
#     "text-generation",
#     model=_TEXT_MODEL,
#     tokenizer=_TOKENIZER,
#     torch_dtype=torch.bfloat16,
#     device_map="auto",
# )

def generate_text(prompt, max_new_tokens=50):
    return "INACTIVE"
    # return _PIPE(
    #     prompt, do_sample=True,
    #     top_k=10,
    #     num_return_sequences=1,
    #     eos_token_id=tokenizer.eos_token_id,
    #     max_new_tokens=max_new_tokens
    # )
