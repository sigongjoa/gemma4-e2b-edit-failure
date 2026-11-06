"""Edit failure with and without exact repeats. A repeat = same task, file and old_string as an earlier failed call.
Usage: distinct.py RUN [RUN...]"""
import json, glob, os, sys, re

RUN = os.environ.get("RUN_DIR", os.environ.get("RUN_DIR", os.path.expanduser("~/gemma4/run")))
T = [0] * 6
for r in sys.argv[1:]:
    calls = fails = rep = 0
    for p in glob.glob(f"{RUN}/{r}/traces/trace_*.json"):
        failed = set()
        for s in json.load(open(p))["steps"]:
            tc = s.get("tool_calls") or []; res = (s.get("observation") or {}).get("results") or []
            for i, t in enumerate(tc):
                if t["function_name"] != "edit_file": continue
                m = [x for x in res if x.get("source_call_id") == t.get("tool_call_id")] or res[i:i + 1]
                out = str(m[0].get("content")) if m else str((s.get("observation") or {}).get("content"))
                a = t.get("arguments") or {}; key = (a.get("filepath"), a.get("old_string"))
                calls += 1
                if re.search(r'"strategy": "\w+"', out): continue
                fails += 1
                if key in failed: rep += 1
                failed.add(key)
    d_calls, d_fails = calls - rep, fails - rep
    print(f"{r:10s} calls {calls:4d} fail {fails:4d} ({fails / max(calls, 1):.0%})  repeats {rep:3d}  "
          f"distinct: calls {d_calls:3d} fail {d_fails:3d} ({d_fails / max(d_calls, 1):.0%})")
