import threading

import model
import tts
from blogcast import script


def work_on(job):
    jtype = job["job_type"]
    assert jtype in {"blogcast", "tts"}  # "image", "caption", "code_summarize"
    jid = job["id"]
    model.update_job(jid, status="RUNNING")
    try:
        if jtype == "tts":
            res = tts.text_to_wavs(**job["input"])
            model.update_job(jid, status="COMPLETE", output=res)
        elif jtype == "blogcast":
            scr = script.script_from(**job["input"])
            model.update_job(jid, status="WAITING_FOR_CHILDREN", output={"script": scr})
            for ln in scr:
                if type(ln) is str:
                    model.new_job(
                        "tts",
                        {"text": ln, "voice": job["input"].get("voice")},
                        parent=jid,
                    )
        if (job["parent_job"] is not None) and model.all_children_finished_p(
            job["parent_job"]
        ):
            model.update_job(job["parent_job"], status="COMPLETE")
    except Exception as e:
        model.update_job(jid, status="ERRORED", output={"error": str(e)})


def _worker():
    work_on(model.get_job())


def make_worker():
    return threading.Thread(_worker, daemon=True)
