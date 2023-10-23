import openai
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

def summarize_code(code_block):
    res = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",
        messages=[
            {"role": "system",
             "content": "You are an omni-competent programmer and brilliant documentation writer. You're usually the stickler that insists on better docstrings being written when you're on a team. You know all programming languages, and have an impeccable skill for explaining code written in them to others. You will be asked to summarize a code block. Assume that this is a description that will have to be read out loud to someone familiar with the language it is written in, but not what the specific code itself does. You should tell the listener what language the code is written in, and what it does at a high level."},
            {"role": "user",
             "content": f"Please summarize the following code block: {code_block}"}])
    return res.choices[0].message

# _TEXT_MODEL = "tiiuae/falcon-7b-instruct"
# _TOKENIZER = AutoTokenizer.from_pretrained(_TEXT_MODEL)
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
