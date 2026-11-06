"""Count edit_file outcomes by matching strategy. Usage: strat.py RUN..."""
import json, glob, os, sys, re, collections
for r in sys.argv[1:]:
    c = collections.Counter()
    for p in glob.glob(os.path.join(os.environ.get("RUN_DIR", os.path.expanduser("~/gemma4/run")), r, "traces", "trace_*.json")):
        for s in json.load(open(p))["steps"]:
            tc = s.get("tool_calls") or []; res = (s.get("observation") or {}).get("results") or []
            for i, t in enumerate(tc):
                if t["function_name"] != "edit_file": continue
                m = [x for x in res if x.get("source_call_id") == t.get("tool_call_id")] or res[i:i+1]
                out = str(m[0].get("content")) if m else str((s.get("observation") or {}).get("content"))
                k = re.search(r'"strategy": "(\w+)"', out)
                c[k.group(1) if k else ("error" if "error" in out else "?")] += 1
    print(r, dict(c))
    if "--peek" in os.environ.get("PEEK",""): print(out[:400])
