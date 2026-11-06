"""Localization stage per run: did the agent read / try to edit / successfully edit a file the reference patch touches?
Usage: locate_stats.py RUN [RUN...]  (dirs under ~/gemma4/run)"""
import json, re, sys, glob, os
RUN = os.environ.get("RUN_DIR", os.path.expanduser("~/gemma4/run"))
T = {json.loads(l)["instance_id"]: json.loads(l) for l in open(os.environ["TASKS_JSONL"])}

def calls(path):
    for s in json.load(open(path))["steps"]:
        tc = s.get("tool_calls") or []; ob = s.get("observation") or {}; res = ob.get("results") or []
        for i, c in enumerate(tc):
            m = [r for r in res if r.get("source_call_id") == c.get("tool_call_id")] or res[i:i + 1]
            yield c.get("function_name"), c.get("arguments") or {}, str(m[0].get("content")) if m else str(ob.get("content"))

for r in sys.argv[1:]:
    n = read = tried = ok = 0
    for p in sorted(glob.glob(f"{RUN}/{r}/traces/trace_*.json")):
        iid = os.path.basename(p)[6:-5]; gold = set(re.findall(r"^\+\+\+ b/(\S+)", T[iid]["patch"], re.M))
        n += 1; R = E = S = False
        for name, a, out in calls(p):
            fp = a.get("filepath") or ""; cmd = a.get("command") or ""
            hit = fp in gold or any(g in cmd for g in gold)
            if name == "read_file" and hit: R = True
            if name == "run_command" and hit and re.search(r"(cat|sed -n|head|tail|nl|grep)", cmd): R = True
            if name == "edit_file" and fp in gold:
                E = True
                if '"status": "ok"' in out: S = True
        read += R; tried += E; ok += S
    print(f"{r}: n={n} read_gold={read} edit_gold_tried={tried} edit_gold_ok={ok}")
