import asyncio
import os

import tqdm
from flask import Flask, abort, jsonify, request, send_from_directory

import basics
import blogcast.script
import tts
import util

app = Flask(__name__)

if not os.path.exists("static"):
    os.makedirs("static")

GPU = asyncio.Lock()

@app.route("/health")
def health():
    return jsonify({"status": "ok"})

@app.post("/v0/audio/transcribe")
async def run_transcribe():
    if 'file' not in request.files:
        return jsonify({"status": "error", "message": "request must have a file"}), 400
    file = request.files['file']
    if file.filename == '':
        return jsonify({"status": "error", "message": "request must have a file"}), 400
    allowed_extensions = {".wav", ".mp3"}
    if not os.path.splitext(file.filename)[1].lower() in allowed_extensions:
        return jsonify({
            "status": "error",
            "message": f"file must be one of {', '.join(allowed_extensions)}"
        }), 400

    path = util.fresh_file("tmp-transcription-audio-", os.path.splitext(file.filename))
    file.save(path)

    async with GPU:
        return jsonify({"status": "ok", "result": basics.transcribe(path)})

@app.get("/v0/audio/tts")
def tts_properties():
    return jsonify({
        "voices": tts.get_voices()
    })

@app.post("/v0/audio/tts")
async def tts_run():
    text = request.values.get('text')
    if text is None:
        return jsonify({"status": "error", "message": "request must have text"}), 400

    voice = request.values.get("voice", "leo")
    k = int(request.values.get("k", "1"))

    async with GPU:
        res = tts.text_to_wavs(text, voice=voice, k=k)

    return jsonify({
        "status": "ok", "voice": voice, "text": text,
        "urls": [f"/static/{os.path.basename(r)}" for r in res]
    })

@app.post("/v0/audio/blogcast")
async def read_blog_post():
    url = request.values.get('url')
    if url is None:
        return jsonify({"status": "error", "message": "request must have a target URL"}), 400

    voice = request.values.get("voice", "leo")

    app.logger.debug(f"blogcast -- reading '{url}' as '{voice}'...")

    async with GPU:
        script = blogcast.script.script_from(url)
        res = [
            {
                "text": el,
                "url": f"/static/{os.path.basename(tts.text_to_wavs(el, voice=voice, k=1)[0])}"
            } if isinstance(el, str) else el
            for el in tqdm.tqdm(script)
        ]

    return jsonify({
        "status": "ok", "voice": voice, "target": url,
        "result": res
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

    async with GPU:
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


########## Blacklist
if os.path.exists("blacklist.txt"):
    with open("blacklist.txt", 'r') as f:
        IP_BLACKLIST = set(f.read().splitlines())
else:
    IP_BLACKLIST = set([])

@app.route("/actuator/gateway/routes")
@app.route("/geoserver")
@app.route("/boaform/admin/formLogin")
@app.route("/portal/redlion")
@app.route("/geoserver/web")
@app.route("/cf_scripts/scripts/ajax/ckeditor/ckeditor.js")
@app.route("/.env")
@app.route("/manager/html")
@app.route("/web_shell_cmd.gch")
def add_to_blacklist():
    ip = request.environ.get("REMOTE_ADDR")
    with open("blacklist.txt", 'a+') as bl:
        bl.write(f"{ip}\n")
    IP_BLACKLIST.add(ip)
    return abort(403)

@app.before_request
def block_by_ip():
    ip = request.environ.get("REMOTE_ADDR")
    if ip in IP_BLACKLIST:
        return abort(403)
##############################
