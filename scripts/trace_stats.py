"""Tool-call behaviour per condition, from ATIF traces. Usage: trace_stats.py A D"""
import json, sys, re, os
from pathlib import Path
from collections import Counter

RUN = Path(os.environ.get("RUN_DIR", Path.home() / "gemma4/run"))


def calls(path):
    """Yield (tool name, arguments, result text) in order."""
    for s in json.load(open(path))["steps"]:
        tc = s.get("tool_calls") or []
        ob = s.get("observation") or {}
        res = ob.get("results") or []
        for i, c in enumerate(tc):
            cid = c.get("tool_call_id")
            m = [r for r in res if r.get("source_call_id") == cid] or res[i:i + 1]
            yield c.get("function_name"), c.get("arguments") or {}, str(m[0].get("content")) if m else str(ob.get("content"))


if len(sys.argv) > 1 and sys.argv[1] == "--peek":
    t = json.load(open(RUN / "pair_D/traces/trace_rich_3772.json"))
    s = [x for x in t["steps"] if x.get("tool_calls")][1]
    print(json.dumps(s, ensure_ascii=False)[:900])
    sys.exit()

for c in sys.argv[1:]:
    tot, edit, efail, retry_same, read_after, followed, pycomp, runs, submit = Counter(), 0, 0, 0, 0, 0, 0, 0, 0
    tasks_pycomp = 0
    for p in sorted((RUN / f"pair_{c}/traces").glob("trace_*.json")):
        seq = list(calls(p))
        tot.update(n for n, _, _ in seq)
        any_py = False
        for k, (n, a, r) in enumerate(seq):
            if n == "submit_patch":
                submit += 1
            if n == "run_command" and "py_compile" in json.dumps(a):
                pycomp += 1
                any_py = True
            if n == "edit_file":
                edit += 1
                if '"status": "ok"' not in r[:200]:
                    efail += 1
                    nxt = seq[k + 1] if k + 1 < len(seq) else None
                    if nxt and nxt[0] == "read_file":
                        read_after += 1
                    if nxt and nxt[0] == "edit_file" and nxt[1].get("old_string") == a.get("old_string"):
                        retry_same += 1
        tasks_pycomp += any_py
    print(c, "edit", edit, "fail", efail, "read_next", read_after, "same_retry", retry_same,
          "py_compile", pycomp, "tasks_py", tasks_pycomp, "submit", submit, dict(tot.most_common(8)))

    fails = Counter()
    for p in (RUN / f"pair_{c}/traces").glob("trace_*.json"):
        for n, a, r in calls(p):
            if n == "edit_file":
                fails[re.sub(r"[\d'`].*", "", r[:70])[:55]] += 1
    print(fails.most_common(6))
