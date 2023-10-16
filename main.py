import os

from flask import Flask, jsonify, request, send_from_directory

import basics
import tts
import util

app = Flask(__name__)

if not os.path.exists("static"):
    os.makedirs("static")

@app.route("/health")
def health():
    return jsonify({"status": "ok"})

@app.post("/v0/audio/transcribe")
def run_transcribe():
    if 'file' not in request.files:
        return jsonify({"status": "error", "message": "request must have a file"}), 400
    file = request.files['file']
    if file.filename == '':
        return jsonify({"status": "error", "message": "request must have a file"}), 400
    if not os.path.splitext(file.filename)[1].lower() == ".wav":
        return jsonify({"status": "error", "message": "file myst be a .wav"}), 400

    path = util.fresh_file("tmp-transcription-audio-", os.path.splitext(file.filename))
    file.save(path)

    return jsonify({"status": "ok", "result": basics.transcribe(path)})

@app.post("/v0/audio/tts")
def run_tts():
    text = request.values.get('text')
    if text is None:
        return jsonify({"status": "error", "message": "request must have text"}), 400

    voice = request.values.get("voice", "leo")
    k = int(request.values.get("k", "1"))

    res = tts.text_to_wavs(text, voice=voice, k=k)


    return jsonify({
        "status": "ok", "voice": voice, "text": text,
        "urls": [f"/static/{os.path.basename(r)}" for r in res]
    })

@app.post("/v0/text/chat")
def run_ai_chat():
    return jsonify({"status": "ok", "stub": "TODO"})

@app.post("/v0/text/generate")
def run_generate_text():
    prompt = request.values.get('prompt')
    if prompt is None:
        return jsonify({"status": "error", "message": "request must have prompt"}), 400
    max_new_tokens = request.values.get("max_new_tokens")

    return jsonify({"status": "ok", "result": basics.generate_text(prompt, max_new_tokens)})

@app.post("/v0/image/describe")
def run_describe():
    url = request.values.get('url')
    if url is None:
        return jsonify({"status": "error", "message": "request must have url"}), 400
    return jsonify({"status": "ok", "result": basics.caption_image(url)})

@app.get("/static/<path:filename>")
def static_file(filename=None):
    return send_from_directory("static", filename)
