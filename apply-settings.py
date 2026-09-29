#!/usr/bin/env python3
"""Merge immich-settings.json into the server's system config.

Usage: IMMICH_API_KEY=... ./apply-settings.py [http://localhost:2283]
Only the keys present in immich-settings.json are changed; everything else
keeps Immich's defaults. Prints what changed.
"""
import json, os, sys, urllib.request

base = (sys.argv[1] if len(sys.argv) > 1 else "http://localhost:2283").rstrip("/") + "/api"
key = os.environ["IMMICH_API_KEY"]
want = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "immich-settings.json")))
want.pop("_comment", None)


def call(method, path, body=None):
    req = urllib.request.Request(base + path, method=method, headers={"x-api-key": key, "Content-Type": "application/json"},
                                 data=json.dumps(body).encode() if body is not None else None)
    with urllib.request.urlopen(req) as r:
        return json.load(r)


def merge(cur, new, path=""):
    for k, v in new.items():
        if k not in cur:
            sys.exit(f"unknown setting: {path}{k}")
        if isinstance(v, dict):
            merge(cur[k], v, f"{path}{k}.")
        elif cur[k] != v:
            print(f"  {path}{k}: {cur[k]!r} -> {v!r}")
            cur[k] = v


cfg = call("GET", "/system-config")
merge(cfg, want)
call("PUT", "/system-config", cfg)
print("applied")
