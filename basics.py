import openai
import PIL
import pyannote.audio
import requests
import torch
import torchaudio
import transformers
import whisper
from transformers import AutoModelForCausalLM, AutoTokenizer, pipeline

import audio
import util


def _transcribe(audio_file):
    model = whisper.load_model("base")
    model.to("cuda")
    audio = whisper.load_audio(audio_file)
    audio = whisper.pad_or_trim(audio)
    mel = whisper.log_mel_spectrogram(audio).to(model.device)
    _, probs = model.detect_language(mel)
    opts = whisper.DecodingOptions()
    return whisper.decode(model, mel, opts)


def transcribe(audio_file):
    return _transcribe(audio_file).text


def speaker_diarize(audio_file):
    model = pyannote.audio.Pipeline.from_pretrained(
        "pyannote/speaker-diarization@2.1", use_auth_token=True
    )
    model.to(torch.device("cuda"))
    loaded = torchaudio.load(audio_file)
    annotation = model({"waveform": loaded[0], "sample_rate": loaded[1]})
    lns = (ln.split() for ln in annotation.to_lab().splitlines())

    return [
        {
            "speaker": label,
            "start": start,
            "end": end,
            "text": transcribe(audio.slice(audio_file, float(start), float(end))),
        }
        for start, end, label in lns
    ]


def transcribe_to_word_srt(audio_file):
    model = whisper.load_model("base")
    res = model.transcribe(audio_file, word_timestamps=True)
    ix = 0
    for seg in res["segments"]:
        for wd in seg["words"]:
            ix += 1
            res = "\n".join(
                [
                    f"{ix}",
                    f"{util.str_timestamp(wd['start'])} --> {util.str_timestamp(wd['end'])}",
                    wd["word"].strip(),
                    "",
                ]
            )
            print(res)


def transcribe_to_srt(audio_file):
    fname = util.fresh_file("transcription-", ".srt")
    writer = whisper.utils.WriteSRT("static")
    model = whisper.load_model("base")
    model.to("cuda")
    res = model.transcribe(audio_file)
    with open(fname, "w") as f:
        writer.write_result(res, f)
    return fname


_CAPTION = None


def caption_image(url):
    global _CAPTION
    if _CAPTION is None:
        print("Loading CAPTION model...")
        _CAPTION = pipeline(
            "image-to-text", model="Salesforce/blip2-flan-t5-xl"
        )  # "Salesforce/blip-image-captioning-base"
    resp = requests.get(url, headers=util.FF_HEADERS, stream=True)
    if resp.status_code == 200:
        img = PIL.Image.open(resp.raw)
        return _CAPTION(img)[0]["generated_text"]
    return ""


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
    # return _INSTRUCT(
    #     prompt,
    #     do_sample=True,
    #     top_k=10,
    #     num_return_sequences=1,
    #     eos_token_id=_TOKENIZER.eos_token_id,
    #     max_new_tokens=max_new_tokens,
    # )


def summarize_code(code_block):
    res = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",
        messages=[
            {
                "role": "system",
                "content": "You are an omni-competent programmer and brilliant documentation writer. You're usually the stickler that insists on better docstrings being written when you're on a team. You know all programming languages, and have an impeccable skill for explaining code written in them to others. You will be asked to summarize a code block. Assume that this is a description that will have to be read out loud to someone familiar with the language it is written in, but not what the specific code itself does. You should tell the listener what language the code is written in, and what it does at a high level. Keep it short; on the order of two to five sentences.",
            },
            {
                "role": "user",
                "content": f"Please summarize the following code block: {code_block}",
            },
        ],
    )
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
