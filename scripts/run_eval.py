"""Runs swegemma with sandboxes that mimic the official Docker setup.

Docker mode injects competition wheels into site-packages; subprocess mode skips that.
This unpacks the harness-selected wheels once and gives each sandbox: task checkout first,
then those wheels. GOLD=1 replaces the agent with the reference patch to validate scoring.
"""
import os
import pathlib
import re
import shutil
import sys
import zipfile

import swegemma.sandbox.subprocess as sandbox
from swegemma.cli import main
if os.environ.get("FUZZY_EDIT"):  # diagnostic: forgiving edit_file anchor (fuzzy_edit.py), not part of the official harness
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); import fuzzy_edit; fuzzy_edit.install()

RUN = pathlib.Path.home() / "gemma4" / "run"
SITE = RUN / "sp_base"


def build_site():
    if (SITE / ".done").exists():
        return
    shutil.rmtree(SITE, ignore_errors=True)
    SITE.mkdir(parents=True)
    best = {}
    for whl in (RUN / "wheels").glob("*.whl"):
        parts = whl.stem.split("-")
        if not ("py3" in parts[-3] or "cp312" in parts[-3]):
            continue
        key = re.sub(r"[-_.]+", "-", parts[0]).lower()
        version = tuple(int(n) for n in re.findall(r"\d+", parts[1]))
        if key not in best or version > best[key][0]:
            best[key] = (version, whl)
    for _, whl in best.values():
        with zipfile.ZipFile(whl) as z:
            z.extractall(SITE)
    (SITE / ".done").write_text("ok")
    print("unpacked packages:", len(best), flush=True)


original_start = sandbox.SubprocessManager.start


def clean_start(self):
    sandbox_id = original_start(self)
    box = self._sandboxes[sandbox_id]
    venv, workspace = box["venv"], box["workspace"]
    for pth in venv.glob("lib/python*/site-packages/_host_env.pth"):
        inherited = pth.read_text(encoding="utf-8")
        pth.write_text(f"{workspace}/src\n{workspace}\n{SITE}\n{RUN}/dev_site\n{inherited}", encoding="utf-8")
    launcher = venv / "bin" / "pytest"
    if not launcher.exists():
        launcher.write_text(f'#!/bin/sh\nexec "{venv}/bin/python3" -m pytest "$@"\n', encoding="utf-8")
        launcher.chmod(0o755)
    return sandbox_id


sandbox.SubprocessManager.start = clean_start

if os.environ.get("GOLD"):
    import swegemma.evaluate as evaluate

    async def gold_patch(self, task, *args, **kwargs):
        return task.patch, None, evaluate.SessionTrace()

    evaluate.Evaluator._run_agent_sandbox = gold_patch

build_site()
sys.exit(main(sys.argv[1:]))
