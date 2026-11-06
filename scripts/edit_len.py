"""edit_file success rate by old_string length (non-blank lines). Usage: edit_len.py RUN [RUN...]"""
import json, glob, os, sys, collections
c = collections.Counter()
for r in sys.argv[1:]:
    for p in glob.glob(os.path.join(os.environ.get("RUN_DIR", os.path.expanduser("~/gemma4/run")), r, "traces", "trace_*.json")):
        for st in json.load(open(p))["steps"]:
            for tc in st.get("tool_calls") or []:
                if tc["function_name"] != "edit_file": continue
                o = json.dumps(st.get("observation"))
                if "Budget" in o or "identical" in o: continue
                n = sum(1 for l in (tc["arguments"].get("old_string") or "").splitlines() if l.strip())
                b = "1" if n <= 1 else "2-3" if n <= 3 else "4-8" if n <= 8 else "9+"
                c[(b, "ok" if "FileEditError" not in o else "fail")] += 1
for b in ["1", "2-3", "4-8", "9+"]:
    ok, f = c[(b, "ok")], c[(b, "fail")]
    print(f"{b:4s} lines: {ok+f:4d} edits, success {ok/(ok+f or 1):.0%}")
