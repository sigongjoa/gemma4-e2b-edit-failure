"""Classify each failed edit_file (old_string not found) by why it did not match.
stale   = matches the file as it was before an earlier successful edit in the same task (model edits a version that no longer exists)
escape  = matches after undoing escape damage (\\" -> ", \n -> newline, \t -> tab)
drift   = most old_string lines exist in order, some differ (model miscopied / rewrote lines)
absent  = little of it exists in the file (wrong file or invented code)
Usage: edit_fail_kinds.py RUN [RUN...]"""
import json, glob, os, sys, tarfile, collections
from adk_eval_core import apply_replacement
RUN = os.environ.get("RUN_DIR", os.path.expanduser("~/gemma4/run"))
kinds = collections.Counter(); ex = collections.defaultdict(list)

def ok(src, old):
    return apply_replacement(src, old, old + "#").error_message is None

def best_run(src, old):
    sl = [l.strip() for l in src.splitlines()]; ol = [l.strip() for l in old.splitlines() if l.strip()]
    if not ol: return 0
    S = set(sl); return sum(l in S for l in ol) / len(ol)

for r in sys.argv[1:]:
    for p in sorted(glob.glob(f"{RUN}/{r}/traces/trace_*.json")):
        iid = os.path.basename(p)[6:-5]
        snaps = glob.glob(f"{RUN}/snapshots/{iid}.tgz")
        if not snaps: continue
        tf = tarfile.open(snaps[0]); names = tf.getnames(); files = {}; history = collections.defaultdict(list)
        for st in json.load(open(p))["steps"]:
            for tc in st.get("tool_calls") or []:
                a = tc.get("arguments") or {}; fp = a.get("filepath")
                if tc["function_name"] not in ("edit_file", "write_file") or not fp: continue
                if fp not in files:
                    m = [x for x in names if x.endswith("/" + fp) or x == fp]
                    files[fp] = tf.extractfile(m[0]).read().decode() if m else None
                if files[fp] is None: continue
                if tc["function_name"] == "write_file":
                    history[fp].append(files[fp]); files[fp] = a.get("content", ""); continue
                old = a.get("old_string", ""); new = a.get("new_string", "")
                res = apply_replacement(files[fp], old, new)
                if res.error_message is None:
                    history[fp].append(files[fp]); files[fp] = res.new_content; continue
                if "not found" not in res.error_message: continue
                unesc = old.replace('\\"', '"').replace("\n", "\n").replace("\t", "\t")
                if any(ok(h, old) for h in history[fp]): k = "stale"
                elif unesc != old and ok(files[fp], unesc): k = "escape"
                elif best_run(files[fp], old) >= 0.5: k = "drift"
                else: k = "absent"
                kinds[k] += 1
                if "\\n" in old or '\\"' in old: kinds[k + "+literal_escape"] += 1  # backslash-n / backslash-quote typed as text
                if len(ex[k]) < 2: ex[k].append((iid, fp, old[:160]))
tot = sum(kinds.values())
for k, v in kinds.most_common(): print(f"{k:7s} {v:4d} {v/tot:.0%}")
for k, v in ex.items():
    for e in v: print("EX", k, e)
