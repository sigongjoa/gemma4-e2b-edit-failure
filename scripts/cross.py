"""For each logged edit failure that offline replay says fuzzy-lands, show the live result + best/second ratio."""
import json, glob, os, sys, tarfile, collections, difflib
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); import fuzzy_edit as F
from adk_eval_core import apply_replacement
RUN = os.environ.get("RUN_DIR", os.path.expanduser("~/gemma4/run")); r = sys.argv[1]; c = collections.Counter()
for p in sorted(glob.glob(f"{RUN}/{r}/traces/trace_*.json")):
    iid = os.path.basename(p)[6:-5]; snaps = glob.glob(f"{RUN}/snapshots/{iid}.tgz")
    if not snaps: continue
    tf = tarfile.open(snaps[0]); names = tf.getnames(); files = {}
    for s in json.load(open(p))["steps"]:
        res = (s.get("observation") or {}).get("results") or []
        for i, tc in enumerate(s.get("tool_calls") or []):
            a = tc.get("arguments") or {}; fp = a.get("filepath")
            if tc["function_name"] not in ("edit_file", "write_file") or not fp: continue
            m = [x for x in res if x.get("source_call_id") == tc.get("tool_call_id")] or res[i:i+1]
            live = str(m[0].get("content")) if m else str((s.get("observation") or {}).get("content"))
            if fp not in files:
                mm = [x for x in names if x.endswith("/" + fp) or x == fp]
                files[fp] = tf.extractfile(mm[0]).read().decode() if mm else None
            if files[fp] is None: continue
            if tc["function_name"] == "write_file": files[fp] = a.get("content", ""); continue
            old, new = a.get("old_string", ""), a.get("new_string", "")
            rr = apply_replacement(files[fp], old, new)
            if rr.error_message is None: files[fp] = rr.new_content; continue
            if "not found" not in rr.error_message: continue
            span = F.fuzzy_find(files[fp], old)
            livek = "fuzzy" if '"fuzzy"' in live else ("notfound" if "not found" in live else ("ok" if '"strategy"' in live else "other"))
            c[(bool(span), livek)] += 1
            if span and livek == "notfound" and c[(True, "notfound")] <= 3:
                print(iid, fp, repr(old[:150])); print("   live:", live[:160])
            if span and livek == "fuzzy":
                if os.environ.get("SHOW"):
                    import ast
                    after = files[fp][:span[0]] + F.unesc(new) + files[fp][span[1]:]
                    def ok(t):
                        try: ast.parse(t); return True
                        except SyntaxError: return False
                    print("##", iid, fp, "parse before", ok(files[fp]), "after", ok(after))
                    print("  OLD :", repr(old[:200])); print("  HIT :", repr(files[fp][span[0]:span[1]][:200])); print("  NEW :", repr(new[:200]))
                files[fp] = files[fp][:span[0]] + F.unesc(new) + files[fp][span[1]:]
print(dict(c))
