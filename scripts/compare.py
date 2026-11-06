"""Compare two condition runs: funnel per task. Usage: compare.py A D"""
import json, re, subprocess, sys, tarfile, tempfile, glob, os
from pathlib import Path

RUN = Path(os.environ.get("RUN_DIR", Path.home() / "gemma4/run"))
TASKS = {json.loads(l)["instance_id"]: json.loads(l) for l in open(os.environ["TASKS_JSONL"])}
FLAG = {"rich_3480", "rich_3471"}  # memory event 11-02 15:00, condition D only


def files(patch):
    return set(re.findall(r"^\+\+\+ b/(\S+)", patch, re.M))


def snapshot(iid, into):
    t = next(iter(glob.glob(str(RUN / "snapshots" / f"{iid}*"))), None) or f"{RUN}/snapshots/{iid}.tgz"
    with tarfile.open(t) as f:
        f.extractall(into, filter="data")
    roots = [p for p in Path(into).iterdir() if p.is_dir()]
    return roots[0] if len(roots) == 1 and not (Path(into) / ".git").exists() else Path(into)


def syntax_broken(iid, patch):
    """True/False, or None if the patch does not apply to the snapshot."""
    with tempfile.TemporaryDirectory() as td:
        root = snapshot(iid, td)
        p = subprocess.run(["patch", "-p1", "-s", "-f"], cwd=root, input=patch, text=True, capture_output=True)
        if p.returncode:
            return None
        for f in files(patch):
            if f.endswith(".py") and (root / f).exists():
                try:
                    compile((root / f).read_text(errors="replace"), f, "exec")
                except (SyntaxError, ValueError):
                    return True
    return False


def load(c):
    d = RUN / f"pair_{c}"
    out = {}
    for l in open(d / "task_results.jsonl"):
        r = json.loads(l)
        i = r["instance_id"]
        pf = d / "patches" / f"{i}.patch"
        patch = pf.read_text(errors="replace") if pf.exists() else ""
        log = d / "logs" / f"{i}.log"
        txt = log.read_text(errors="replace") if log.exists() else ""
        r["patch"] = patch
        r["empty"] = not patch.strip()
        r["hit"] = bool(files(patch) & files(TASKS[i]["patch"]))
        r["syntax"] = syntax_broken(i, patch) if patch.strip() else False
        r["edit_fail"] = len(re.findall(r"old_string[^\n]{0,40}not found|not found[^\n]{0,40}old_string", txt))
        out[i] = r
    return out


def line(name, rows):
    n = len(rows)
    return (f"{name}: n={n} resolved={sum(r['resolved'] for r in rows)} patch={sum(not r['empty'] for r in rows)} "
            f"empty={sum(r['empty'] for r in rows)} goldfile={sum(r['hit'] for r in rows)} "
            f"syntax={sum(r['syntax'] is True for r in rows)} noapply={sum(r['syntax'] is None for r in rows)} "
            f"editfail={sum(r['edit_fail'] for r in rows)} errors={sum(bool(r['error']) for r in rows)} "
            f"sec={sum(r['duration_seconds'] for r in rows):.0f} calls={sum(r['tool_calls'] for r in rows)}")


a, d = load(sys.argv[1]), load(sys.argv[2])
assert set(a) == set(d)
print(line("A", list(a.values())))
print(line("D", list(d.values())))
keep = [i for i in a if i not in FLAG]
print(line("A-flag", [a[i] for i in keep]))
print(line("D-flag", [d[i] for i in keep]))
for i in sorted(a):
    x, y = a[i], d[i]
    print(f"{i:15} A res={x['resolved']:d} sz={x['agent_patch_size']:5} hit={x['hit']:d} syn={x['syntax']!s:5} ef={x['edit_fail']:2} "
          f"| D res={y['resolved']:d} sz={y['agent_patch_size']:5} hit={y['hit']:d} syn={y['syntax']!s:5} ef={y['edit_fail']:2} {str(y['error'] or '')[:38]}")
same = sum(a[i]["empty"] == d[i]["empty"] and a[i]["hit"] == d[i]["hit"] and a[i]["syntax"] == d[i]["syntax"] for i in a)
print("identical funnel stage:", same, "of", len(a))
print({str(k): v for k, v in __import__("collections").Counter(re.sub(r"\d+", "N", str(r["error"]))[:45] for r in a.values()).items()})
print({str(k): v for k, v in __import__("collections").Counter(re.sub(r"\d+", "N", str(r["error"]))[:45] for r in d.values()).items()})
