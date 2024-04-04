import PIL
import pyannote.audio
import requests
import torch
import torchaudio
import transformers
import whisper
from transformers import AutoTokenizer, pipeline

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


_FALCON7B = None


def _load_falcon():
    global _FALCON7B
    if _FALCON7B is None:
        print("Loading FALCON7B...")
        text_model = "tiiuae/falcon-7b-instruct"
        tokr = AutoTokenizer.from_pretrained(text_model)
        _FALCON7B = transformers.pipeline(
            "text-generation",
            model=text_model,
            tokenizer=tokr,
            torch_dtype=torch.bfloat16,
            device_map=util.dev_by(name="4090"),
        )


def _prompt_text(prompt, max_new_tokens, pipe):
    res = pipe(
        prompt,
        do_sample=True,
        top_k=10,
        num_return_sequences=1,
        max_new_tokens=max_new_tokens,
    )
    return res[0]["generated_text"][len(prompt) :].strip()


def falcon_complete(prompt, max_new_tokens=50):
    _load_falcon()
    return _prompt_text(prompt, max_new_tokens, _FALCON7B)


CODE_IDENTIFY = pipeline(
    "text-classification", model="huggingface/CodeBERTa-language-id"
)


def summarize_code(code_block):
    kfn = lambda el: el["score"]
    lang = sorted(CODE_IDENTIFY(code_block), key=kfn, reverse=True)[0]["label"]
    summary = falcon_complete(
        f"Here's some code: \n```{code_block}```\n\n To summarize in a plain English sentence, it does: ",
        250,
    )
    return f"Written in {lang}. {summary}"
