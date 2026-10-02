#!/usr/bin/env python3
"""Keep Immich's background queues moving (checks every 20 minutes).

- resumes any paused queue
- if a queue still has waiting jobs but its count has not changed for
  3 checks in a row (1 hour), restarts the immich-server container
  (at most once every 2 hours)
- logs new kernel I/O errors for sda (SMR drive stalls)
- when every queue is empty, queues "missing" jobs once to catch anything
  dropped by failures, then exits when the queues are empty again
  (or after MAX_HOURS)

Usage: IMMICH_API_KEY=... ./queue-keeper.py   (log: queue-keeper.log next to this file)
"""
import json, os, subprocess, time, urllib.request
from datetime import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
API = "http://localhost:2283/api"
KEY = os.environ["IMMICH_API_KEY"]
INTERVAL = 20 * 60
STUCK_CHECKS = 3
RESTART_GAP = 2 * 3600
MAX_HOURS = 24
MISSING = ("metadataExtraction", "sidecar", "thumbnailGeneration", "smartSearch",
           "faceDetection", "ocr", "videoConversion")
LOG = open(os.path.join(HERE, "queue-keeper.log"), "a", buffering=1)


def log(msg):
    LOG.write(f"[{datetime.now():%m-%d %H:%M}] {msg}\n")


def api(method, path, body=None):
    req = urllib.request.Request(API + path, method=method,
                                 headers={"x-api-key": KEY, "Content-Type": "application/json"},
                                 data=json.dumps(body).encode() if body is not None else None)
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.load(r)


def restart_server():
    subprocess.run(["docker", "compose", "restart", "immich-server"], cwd=HERE, capture_output=True)
    for _ in range(60):
        try:
            api("GET", "/server/ping")
            return
        except Exception:
            time.sleep(5)


def kernel_io_errors(since):
    out = subprocess.run(["journalctl", "-k", "--since", since], capture_output=True, text=True).stdout
    return [l for l in out.splitlines() if "I/O error, dev sda" in l or "ata5: hard resetting" in l]


def main():
    log("queue keeper started")
    start, last_restart, missing_done = time.time(), 0.0, False
    history = {}  # queue -> list of recent waiting counts
    last_check = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    while time.time() - start < MAX_HOURS * 3600:
        try:
            jobs = api("GET", "/jobs")
        except Exception as e:
            log(f"API error: {e}")
            time.sleep(INTERVAL)
            continue
        for name, v in jobs.items():
            if v["queueStatus"]["isPaused"]:
                api("PUT", f"/jobs/{name}", {"command": "resume", "force": False})
                log(f"resumed paused queue {name}")
        waiting = {n: v["jobCounts"]["waiting"] for n, v in jobs.items()}
        busy = {n: w for n, w in waiting.items() if w or jobs[n]["jobCounts"]["active"]}
        log("waiting: " + (" ".join(f"{n}={w}" for n, w in busy.items()) or "all queues empty"))

        stuck = []
        for n, w in waiting.items():
            h = history.setdefault(n, [])
            h.append(w)
            del h[:-STUCK_CHECKS]
            if w and len(h) == STUCK_CHECKS and len(set(h)) == 1:
                stuck.append(n)
        if stuck and time.time() - last_restart > RESTART_GAP:
            log(f"no progress for 1 h in {stuck} -> restarting immich-server")
            restart_server()
            last_restart = time.time()
            history.clear()

        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        errs = kernel_io_errors(last_check)
        if errs:
            log(f"{len(errs)} new sda kernel errors, e.g. {errs[-1][-120:]}")
        last_check = now

        if not busy:
            if missing_done:
                log("all queues empty after missing pass -> done")
                return
            for q in MISSING:
                try:
                    api("PUT", f"/jobs/{q}", {"command": "start", "force": False})
                except Exception as e:
                    log(f"could not queue missing {q}: {e}")
            missing_done = True
            log("queues empty -> queued 'missing' jobs once")
        time.sleep(INTERVAL)
    log(f"stopping after {MAX_HOURS} h")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        log(f"CRASHED: {e!r}")
        raise
