import os

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

    voice = request.values.get("voice", "leo")
    k = request.values.get("k", 1)

    res = tts.text_to_wavs(text, voice=voice, k=k)


    return jsonify({
        "status": "ok", "voice": voice, "text": text,
        "urls": [f"/static/{os.path.basename(r)}" for r in res]
    })


@app.get("/static/<path:filename>")
def static_file(filename=None):
    return send_from_directory("static", filename)
