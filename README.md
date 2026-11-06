# Where a 2B Coding Agent Breaks — code and trajectories

Companion material for the Kaggle *Gemma 4 Developer Agent* Paper Track write-up
"Where a 2B Coding Agent Breaks: Edit Execution, Not Harness Configuration, Bounds Gemma 4 E2B on One Consumer GPU".

Gemma 4 E2B (QAT q4_0 GGUF, Ollama, one RTX 3050 8 GB) runs the competition's `swegemma` harness on `rich` issue-fixing tasks.
We measure where each task-run is lost (read the right file → edit it → edit lands → tests pass) and why edits fail.
`RESULTS.md` summarises every condition and the numbers used in the paper.

## Contents

| Path | What |
|---|---|
| `agent_configs/condition_*/` | ADK agent configs for conditions A–K (system prompts, sub-agents, distilled rules) |
| `scripts/` | Runner and analysis scripts (below) |
| `runs/` | Trajectories (`traces/`), agent patches, agent logs, per-task results for every run |
| `RESULTS.md` | Conditions, runs, and results |

Runs: `pair_A`, `pair_D` are conditions A and D on 28 tasks; `sk_<COND>_r<N>` are runs on the 13 evaluation tasks
(`scripts/eval13.txt`); `*_rsmoke` are single-task trials. `pair_<name>` links are the aliases the analysis scripts use.
`sk_K_r2` is kept for completeness but excluded from the paper (9 of 13 tasks timed out while the machine was short of memory).

## Not included (Competition Data)

The competition rules do not allow redistributing Competition Data, which includes the task file, the repository
snapshots and the harness packages. Therefore:

- `tasks.jsonl`, repository snapshots and hidden-test outputs (`test_outputs/`) are omitted.
- Task problem statements are removed from trajectories and logs, including lines the model quoted
  (replaced by `[problem statement removed …]` / `[quoted problem-statement line removed]`).
- `swegemma`, `adk_eval_core`, `adk_submission` wheels are not included. Get them, and the task data, from the competition page.
- Raw `rich` review comments used to distill condition B's rules are not included; the distilled rules are.

## Reproducing

Environment: WSL2 Ubuntu, Python 3.12 venv with the competition wheels and `google-adk`, Ollama serving
`hf.co/google/gemma-4-E2B-it-qat-q4_0-gguf` (see `scripts/eval_config.yaml`).

```bash
export RUN_DIR=$PWD/runs                       # or your own run directory
export TASKS_JSONL=/path/to/competition/tasks.jsonl
# snapshots: put the competition repository snapshots at $RUN_DIR/snapshots/<instance_id>.tgz

python scripts/locate_stats.py sk_H_r1          # stages L1 / L2 / E per run
python scripts/trace_stats.py H D_r2            # edit calls, failures, re-reads, retries
python scripts/compare.py D_r2 H                # funnel per task (needs snapshots)
python scripts/replay_edits.py pair_D           # replay edit calls on snapshots (needs snapshots)
python scripts/edit_fail_kinds.py pair_A pair_D sk_D_r2 sk_B_r1 sk_C_r1   # failure classes
python scripts/edit_len.py pair_A               # success by old_string length
python scripts/strat.py sk_K_r1                 # edit outcomes by matching strategy
python scripts/cross.py sk_K_r1                 # forgiving-matcher replay vs live outcome
python scripts/fuzzy_edit.py --test             # matcher self-test
```

New runs: `SRC=<folder with agent_configs/ and data/tasks.jsonl> PLAN="H:1" TASKS_FILE=eval13.txt bash scripts/skill_runs.sh`.
Condition K additionally needs `FUZZY_EDIT=1`, which makes `run_eval.py` load `fuzzy_edit.py` into the harness.
K is a local diagnostic only; the competition does not allow replacing built-in tools.

## License

Apache License 2.0 (`LICENSE`). Trajectories contain excerpts of the `rich` source code (MIT, © Will McGugan).
