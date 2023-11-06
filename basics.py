import openai
import torch
import transformers
import whisper
from transformers import AutoModelForCausalLM, AutoTokenizer, pipeline

import util


def transcribe(audio_file, gpu="1080"):
    pipe = whisper.load_model("base")
    util.to_gpu(pipe, gpu)
    audio = whisper.load_audio(audio_file)
    audio = whisper.pad_or_trim(audio)
    mel = whisper.log_mel_spectrogram(audio).to(_WHISPER.device)

    _, probs = _WHISPER.detect_language(mel)
    opts = whisper.DecodingOptions()

    result = whisper.decode(_WHISPER, mel, opts)

    return result.text

_CAPTION = None

def caption_image(url):
    if _CAPTION is None:
        print("Loading CAPTION model...")
        _CAPTION = pipeline("image-to-text", model="Salesforce/blip2-flan-t5-xl") # "Salesforce/blip-image-captioning-base"
    return _CAPTION(url)[0]['generated_text']

# print("Loading INSTRUCT...")
# _TEXT_MODEL = "tiiuae/falcon-7b-instruct"
# _TOKENIZER = AutoTokenizer.from_pretrained(_TEXT_MODEL)
# _INSTRUCT = transformers.pipeline(
#     "text-generation",
#     model=_TEXT_MODEL,
#     tokenizer=_TOKENIZER,
#     torch_dtype=torch.bfloat16,
#     device_map=util.dev_by(name="3050"),
# )


def generate_text(prompt, max_new_tokens=50):
    return None
    return _INSTRUCT(
        prompt, do_sample=True,
        top_k=10,
        num_return_sequences=1,
        eos_token_id=_TOKENIZER.eos_token_id,
        max_new_tokens=max_new_tokens
    )

def summarize_code(code_block):
    res = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",
        messages=[
            {"role": "system",
             "content": "You are an omni-competent programmer and brilliant documentation writer. You're usually the stickler that insists on better docstrings being written when you're on a team. You know all programming languages, and have an impeccable skill for explaining code written in them to others. You will be asked to summarize a code block. Assume that this is a description that will have to be read out loud to someone familiar with the language it is written in, but not what the specific code itself does. You should tell the listener what language the code is written in, and what it does at a high level. Keep it short; on the order of two to five sentences."},
            {"role": "user",
             "content": f"Please summarize the following code block: {code_block}"}])
    return res.choices[0].message.content

# def summarize_code(code_block, max_new_tokens=200):
#     res = _INSTRUCT(
#         f"You are an omni-competent programmer and brilliant documentation writer. You're usually the stickler that insists on better docstrings being written when you're on a team. You know all programming languages, and have an impeccable skill for explaining code written in them to others. When asked to write a five-to-eight-sentence summarizing documentation, including a basic note on which language it's written in, on the code {code_block}, you would write:", do_sample=True,
#         top_k=10,
#         num_return_sequences=1,
#         eos_token_id=_TOKENIZER.eos_token_id,
#         max_new_tokens=max_new_tokens
#     )
#     return res[0]["generated_text"]
