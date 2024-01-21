import datetime
import json
import queue
from queue import Queue

from pytrivialsql import sqlite

DB = sqlite.Sqlite3("catwalk.db")

__JOB_QUEUE = Queue()
JOB_STATUS = [
    "STARTED",
    "RUNNING",
    "WAITING_FOR_CHILDREN",
    "CANCELLED",
    "COMPLETE",
    "ERRORED",
]


def init():
    DB.create(
        "jobs",
        [
            "id INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL",
            "parent_job INTEGER",
            "job_type TEXT",
            "input TEXT",
            "output TEXT",
            "status TEXT",
            "created DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL",
            "updated DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL",
        ],
    )


def _transform_job(raw_job):
    raw_job["input"] = json.loads(raw_job["input"])
    if outp := raw_job["output"]:
        raw_job["output"] = json.loads(outp)
    # for dttype in ["created", "updated"]:
    #     if type(val := raw_job[dttype]) is str:
    #         raw_job[dttype] = datetime.datetime.fromisoformat(val)
    return raw_job


def all_jobs():
    return DB.select("jobs", "*", transform=_transform_job)


def jobs_by_id(ids):
    return DB.select("jobs", "*", where={"id": set(ids)}, transform=_transform_job)


def job_tree():
    node_map = {}
    res = []
    job_list = all_jobs()
    for job in job_list:
        job["children"] = []
        if job["parent_job"] is None:
            res.append(job)
        else:
            try:
                node_map[job["parent_job"]]["children"].append(job)
            except KeyError:
                pass
        node_map[job["id"]] = job
    return res


def job_by_id(job_id):
    return DB.select("jobs", "*", where={"id": job_id}, transform=_transform_job)[0]


def all_children_finished_p(job_id):
    children_status = DB.select("jobs", ["status"], where={"parent_job": job_id})
    if {c["status"] for c in children_status} - {"COMPLETE", "ERRORED", "CANCELLED"}:
        return False
    return True


def jobs_by_parent(job_id):
    return DB.select(
        "jobs", "*", where={"parent_job": job_id}, transform=_transform_job
    )


def job_tree_by_id(job_id):
    job = job_by_id(job_id)
    job["children"] = jobs_by_parent(job_id)
    return job


def refill_queue():
    """Meant to be run on startup. It re-populates the job queue with
    jobs still on disk, but not yet comlpeted"""
    queuable = DB.select(
        "jobs",
        "*",
        where=[
            ("NOT", {"status": {"COMPLETE", "CANCELLED", "WAITING_FOR_CHILDREN"}}),
            {"status": None},
        ],
        transform=_transform_job,
    )
    for job in queuable:
        __JOB_QUEUE.put(job["id"])


def new_job(job_type, job_input, parent=None):
    now = datetime.datetime.now()
    props = {
        "job_type": job_type,
        "input": json.dumps(job_input),
        "created": now,
        "updated": now,
    }
    if parent is not None:
        assert job_by_id(parent), f"No such job: {parent}"
        props["parent_job"] = parent
    job_id = DB.insert("jobs", **props)
    job = job_by_id(job_id)
    __JOB_QUEUE.put(job["id"])
    return job


def update_job(job_id, input=None, output=None, status=None):
    update = {}
    if input is not None:
        update["input"] = json.dumps(input)
    if output is not None:
        update["output"] = json.dumps(output)
    if status is not None:
        assert status in JOB_STATUS
        update["status"] = status
    if update:
        update["updated"] = datetime.datetime.now()
        DB.update("jobs", update, where={"id": job_id})
        return job_by_id(job_id)
    return None


def queue_job(job_id):
    assert job_by_id(job_id), f"No such job: {job_id}"
    __JOB_QUEUE.put(job_id)


def pull_job():
    jid = __JOB_QUEUE.get()
    job = job_by_id(jid)
    if not job["status"] == "CANCELLED":
        return job
    return pull_job()


def get_job():
    try:
        jid = __JOB_QUEUE.get_nowait()
        job = job_by_id(jid)
        if not job["status"] == "CANCELLED":
            return job
        return get_job()
    except queue.Empty:
        return None
