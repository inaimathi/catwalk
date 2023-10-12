import os
import tempfile

from flask import Flask, jsonify, request, send_from_directory

import tts

app = Flask(__name__)

if not os.path.exists("static"):
    os.makedirs("static")

@app.route("/health")
def health():
    return jsonify({"status": "ok"})

@app.post("/v0/audio/tts")
def run_tts():
    text = request.values.get('text')
    if text is None:
        return jsonify({"status": "error", "message": "request must have text"}), 400

    voice = request.values.get("voice", "v2/en_speaker_6")

    _, fname= tempfile.mkstemp(prefix="audio-", suffix=".wav", dir="static")
    res = tts.text_to_wav(fname, text, voice=voice)


    return jsonify({
        "status": "ok", "voice": voice, "text": text,
        "url": f"/static/{os.path.basename(res)}"
    })


@app.get("/static/<path:filename>")
def static_file(filename=None):
    return send_from_directory("static", filename)
