"""Where do the wrong lines of a failed old_string come from? Distinct failed calls only (same task, file, old_string counted once).
For each old_string line that is not in the current file:
  in_new   = it also appears in new_string (the model wrote changed code into old_string)
  near     = a file line is >= 0.8 similar (a miscopy of a real line)
  other    = neither (invented, or from another file)
Also: share of distinct failures the forgiving matcher (fuzzy_edit.fuzzy_find) would land.
Usage: why_drift.py RUN [RUN...]"""
import json, glob, os, sys, tarfile, collections, difflib
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from adk_eval_core import apply_replacement
import fuzzy_edit as F

RUN = os.environ.get("RUN_DIR", os.environ.get("RUN_DIR", os.path.expanduser("~/gemma4/run")))
cls = collections.Counter(); src_lines = collections.defaultdict(collections.Counter); fz = collections.Counter(); seen = set()


def ok(src, old):
    return apply_replacement(src, old, old + "#").error_message is None


for r in sys.argv[1:]:
    for p in sorted(glob.glob(f"{RUN}/{r}/traces/trace_*.json")):
        iid = os.path.basename(p)[6:-5]
        snaps = glob.glob(f"{RUN}/snapshots/{iid}.tgz")
        if not snaps: continue
        tf = tarfile.open(snaps[0]); names = tf.getnames(); files = {}; hist = collections.defaultdict(list)
        for st in json.load(open(p))["steps"]:
            for tc in st.get("tool_calls") or []:
                a = tc.get("arguments") or {}; fp = a.get("filepath")
                if tc["function_name"] not in ("edit_file", "write_file") or not fp: continue
                if fp not in files:
                    m = [x for x in names if x.endswith("/" + fp) or x == fp]
                    files[fp] = tf.extractfile(m[0]).read().decode() if m else None
                if files[fp] is None: continue
                if tc["function_name"] == "write_file":
                    hist[fp].append(files[fp]); files[fp] = a.get("content", ""); continue
                old, new = a.get("old_string", ""), a.get("new_string", "")
                res = apply_replacement(files[fp], old, new)
                if res.error_message is None:
                    hist[fp].append(files[fp]); files[fp] = res.new_content; continue
                if "not found" not in res.error_message or (r, iid, fp, old) in seen: continue
                seen.add((r, iid, fp, old))
                ol = [l.strip() for l in F.unesc(old).splitlines() if l.strip()]
                if not ol: continue
                fl = [l.strip() for l in files[fp].splitlines()]; S = set(fl)
                nl = {l.strip() for l in F.unesc(new).splitlines() if l.strip()}
                frac = sum(l in S for l in ol) / len(ol)
                k = "stale" if any(ok(h, old) for h in hist[fp]) else ("altered" if frac >= 0.5 else "absent")
                cls[k] += 1
                fz[(k, F.fuzzy_find(files[fp], old) is not None)] += 1
                if k == "stale": continue
                for l in ol:
                    if l in S: continue
                    if l in nl: src_lines[k]["in_new"] += 1
                    elif difflib.get_close_matches(l, fl, n=1, cutoff=0.8): src_lines[k]["near"] += 1
                    else: src_lines[k]["other"] += 1

print("distinct failures", dict(cls), "total", sum(cls.values()))
for k in ("altered", "absent", "stale"):
    n = cls[k]; print(f"{k:8s} fuzzy-landable {fz[(k, True)]}/{n} ({fz[(k, True)] / max(n, 1):.0%})")
for k, c in src_lines.items():
    t = sum(c.values()); print(f"{k:8s} wrong lines {t}: " + ", ".join(f"{x} {v} ({v / t:.0%})" for x, v in c.most_common()))
