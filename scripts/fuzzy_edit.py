"""Forgiving anchor for edit_file: when old_string is not found exactly, find the window of the current file
whose lines best match old_string's lines and replace it, if the match is close and unambiguous.
Used two ways: offline replay over logged failures (python fuzzy_edit.py RUN...), and as a drop-in patch of
swegemma.edit.apply_replacement for live runs (install())."""
import difflib, json, glob, os, sys, tarfile, collections

THRESH, MARGIN = float(os.environ.get("FZ_T", 0.85)), float(os.environ.get("FZ_M", 0.05))  # ponytail: fixed cutoffs, tune on the 6 tuning tasks if they matter


def unesc(s):
    return s.replace('\\"', '"').replace("\\n", "\n").replace("\\t", "\t") if ("\\n" in s or '\\"' in s) else s


def fuzzy_find(src, old):
    """Return (start, end) char span of the best-matching line window, or None."""
    ol = [l.strip() for l in unesc(old).splitlines() if l.strip()]
    if not ol:
        return None
    lines = src.splitlines(keepends=True)
    st = [l.strip() for l in lines]
    best, second, at = 0.0, 0.0, None
    n = len(ol)
    for i in range(len(lines)):
        # window = next n non-blank lines starting at i
        if not st[i]:
            continue
        idx, j = [], i
        while j < len(lines) and len(idx) < n:
            if st[j]:
                idx.append(j)
            j += 1
        if len(idx) < n:
            break
        r = sum(difflib.SequenceMatcher(None, a, st[k]).ratio() for a, k in zip(ol, idx)) / n
        if r > best:
            best, second, at = r, best, (idx[0], idx[-1])
        elif r > second:
            second = r
    if at is None or best < THRESH or best - second < MARGIN:
        return None
    a = sum(len(l) for l in lines[:at[0]])
    b = sum(len(l) for l in lines[:at[1] + 1])
    if src[b - 1:b] == "\n" and not old.endswith("\n"):
        b -= 1
    return a, b


def install():
    """Patch the harness so edit_file falls back to fuzzy_find on 'not found'."""
    # workspace.edit_file does `from swegemma.edit import apply_replacement` at call time, so patching the module attribute is enough.
    import swegemma.edit as E
    orig = E.apply_replacement

    def patched(content, old_string, new_string, filepath="file", allow_multiple=False):
        try:
            return orig(content, old_string, new_string, filepath=filepath, allow_multiple=allow_multiple)
        except ValueError as e:
            if "not found" not in str(e).lower():
                raise
            span = fuzzy_find(content, old_string)
            if span is None:
                raise
            new = content[:span[0]] + unesc(new_string) + content[span[1]:]
            return E.AppliedEdit(new_content=new, diff=E.make_diff(content, new, filepath), strategy="fuzzy")
    E.apply_replacement = patched


def _selftest():
    src = "def f(x):\n    a = x + 1\n    return a\n\ndef g():\n    pass\n"
    # one altered character in the copied line still lands on the right line
    s = fuzzy_find(src, "    a = x + 2\n    return a")
    assert s and src[s[0]:s[1]] == "    a = x + 1\n    return a", s
    assert fuzzy_find(src, "totally unrelated text here") is None


if __name__ == "__main__" and sys.argv[1:] == ["--test"]:
    _selftest(); print("selftest ok"); sys.exit()

if __name__ == "__main__":
    from adk_eval_core import apply_replacement
    RUN = os.environ.get("RUN_DIR", os.path.expanduser("~/gemma4/run"))
    c = collections.Counter()
    for r in sys.argv[1:]:
        for p in sorted(glob.glob(f"{RUN}/{r}/traces/trace_*.json")):
            iid = os.path.basename(p)[6:-5]
            snaps = glob.glob(f"{RUN}/snapshots/{iid}.tgz")
            if not snaps:
                continue
            tf = tarfile.open(snaps[0]); names = tf.getnames(); files = {}; hist = collections.defaultdict(list)
            for s in json.load(open(p))["steps"]:
                for tc in s.get("tool_calls") or []:
                    a = tc.get("arguments") or {}; fp = a.get("filepath")
                    if tc["function_name"] not in ("edit_file", "write_file") or not fp:
                        continue
                    if fp not in files:
                        m = [x for x in names if x.endswith("/" + fp) or x == fp]
                        files[fp] = tf.extractfile(m[0]).read().decode() if m else None
                    if files[fp] is None:
                        continue
                    if tc["function_name"] == "write_file":
                        files[fp] = a.get("content", ""); continue
                    old, new = a.get("old_string", ""), a.get("new_string", "")
                    res = apply_replacement(files[fp], old, new)
                    if res.error_message is None:
                        hist[fp].append(files[fp]); files[fp] = res.new_content; c["exact"] += 1; continue
                    if "not found" not in res.error_message:
                        c["other_error"] += 1; continue
                    stale = any(apply_replacement(h, old, old + "#").error_message is None for h in hist[fp])
                    span = fuzzy_find(files[fp], old)
                    c[("stale_" if stale else "") + ("fuzzy_lands" if span else "still_fails")] += 1
    tot = sum(v for k, v in c.items() if k not in ("exact", "other_error"))
    for k, v in c.most_common():
        print(f"{k:22s} {v:4d}" + (f" {v / tot:.0%} of failures" if k not in ("exact", "other_error") else ""))
