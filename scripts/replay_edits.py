"""Replay each logged edit_file call, in order, on a copy of the task snapshot.
Does the logged argument reproduce the logged outcome? Usage: replay_edits.py RUN [RUN...]"""
import json, glob, os, sys, tarfile, collections
from adk_eval_core import apply_replacement
RUN = os.environ.get("RUN_DIR", os.path.expanduser("~/gemma4/run"))
agree = collections.Counter(); examples = []
for r in sys.argv[1:]:
    for p in sorted(glob.glob(f"{RUN}/{r}/traces/trace_*.json")):
        iid = os.path.basename(p)[6:-5]
        snaps = glob.glob(f"{RUN}/snapshots/{iid}.tgz")
        if not snaps: continue
        tf = tarfile.open(snaps[0]); names = tf.getnames(); files = {}
        for st in json.load(open(p))["steps"]:
            for tc in st.get("tool_calls") or []:
                a = tc.get("arguments") or {}; fp = a.get("filepath")
                if tc["function_name"] not in ("edit_file", "write_file") or not fp: continue
                if fp not in files:
                    m = [x for x in names if x.endswith("/" + fp) or x == fp]
                    files[fp] = tf.extractfile(m[0]).read().decode() if m else None
                if tc["function_name"] == "write_file":
                    files[fp] = a.get("content", ""); continue
                o = json.dumps(st.get("observation"))
                logged = "nf" if "not found" in o else ("ok" if "FileEditError" not in o and "Budget" not in o else "x")
                if logged == "x" or files[fp] is None: continue
                res = apply_replacement(files[fp], a.get("old_string", ""), a.get("new_string", ""))
                rep = "ok" if res.error_message is None else ("nf" if "not found" in res.error_message else "err")
                if rep == "ok": files[fp] = res.new_content  # keep file state in step with the run
                agree[(r, "logged_" + logged, "replay_" + rep)] += 1
                if logged == "nf" and rep == "ok" and len(examples) < 3: examples.append((iid, fp, a["old_string"][:200]))
for k in sorted(agree): print(k, agree[k])
for e in examples: print("EXAMPLE", e)
