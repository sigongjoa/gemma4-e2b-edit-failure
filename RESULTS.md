# Results

Model: Gemma 4 E2B instruction-tuned, Google QAT q4_0 GGUF on Ollama, one RTX 3050 8 GB, offline.
Limits per task: 7 minutes, 30 tool calls, 60 turns, 120 s per command. Resolved = hidden tests pass in our local sandbox.
Each condition's prediction was written down before it ran; outcomes are reported as they came out.

## Task sets

- 52 public tasks sampled with seed 42; 28 whose reference patch passes in our sandbox (rich 19, requests 5, fastapi 3, httpx 1).
- `rich` tasks created after 2024-08-26 (13, `scripts/eval13.txt`) are the evaluation set for all configuration comparisons.
  The 6 earlier `rich` tasks were reserved for building project rules.

## Conditions

| Cond. | Configuration | Runs |
|---|---|---|
| A | Generic prompt | `pair_A` (28 tasks) |
| D | A + edit-failure recovery and verify-before-submit instructions | `pair_D` (28), `sk_D_r2`, `sk_D_r3` |
| B | D + rules distilled by E2B from 640 `rich` review comments, CONTRIBUTING, CHANGELOG (before 2024-08-26) | `sk_B_r1`, `sk_B_r2` |
| C | D + rules distilled by E2B from 23 online sources | `sk_C_r1` |
| E | Line-addressed editing (skill script / `write_file`+`sed` / `sed` only), single-task trials E1–E3 | `sk_E_rsmoke` |
| F, F2 | Root agent has no edit tools; an `editor` sub-agent (fresh context, `read_file`/`edit_file`) edits. F2 adds a `git diff` check | `sk_F_rsmoke`, `sk_F2_r1` |
| G | D − `write_file` | `sk_G_r1` |
| H | G + reasoning budget 4,096 → 1,024 | `sk_H_r1`–`r3` |
| I | H + reasoning off | `sk_I_r1` |
| J | H + temperature 0.2 → 0 | `sk_J_r1` |
| K | H + forgiving `edit_file` matcher (`fuzzy_edit.py`, local diagnostic only) | `sk_K_r1`, `sk_K_r3` (`sk_K_r2` excluded: 9/13 timeouts under memory pressure) |

## 13 evaluation tasks

| Cond. | Patch | Empty | Broken syntax | Edit fail (failed / all `edit_file`) | Resolved |
|---|---|---|---|---|---|
| D (2 runs) | 8, 10 | 5, 3 | 3, 2 | 90%, 85% | 0 |
| B | 11 | 2 | 1 | 87% | 0 |
| C | 11 | 2 | 2 | 81% | 0 |
| G | 10 | 3 | 4 | 79% (100/127) | 0 |
| H (3 runs) | 11, 8, 11 | 2, 5, 2 | 1, 2, 1 | 87%, 90%, 79% | 0 |
| I | 9 | 4 | 3 | 88% (98/111) | 0 |
| J | 8 | 5 | 3 | 91% (104/114) | 0 |
| F2 | 1 | 12 | 0 | — | 0 |
| K (2 runs) | 11, 11 | 2, 2 | 6, 3 | 82% (90/110), 70% (45/64) | 0 |

On 28 tasks, A resolved 1 (`rich_3006`); D resolved 0.

## Stage funnel (130 task-runs: D ×2, B, C, G, H ×3, I, J on the 13 tasks)

| Stage | Task-runs | Share |
|---|---|---|
| L1 read a file the reference patch changes | 82 | 63% |
| L2 called `edit_file` on it | 55 | 42% |
| E at least one such edit landed | 37 | 28% |
| Resolved | 0 | 0% |

## Edit-failure classes (608 "old_string not found" calls; `pair_A`, `pair_D`, `sk_D_r2`, `sk_B_r1`, `sk_C_r1`)

Replay on snapshots: all 596 logged "not found" failures in the replayed runs also fail on replay.

| Class | Calls | Share |
|---|---|---|
| Altered — ≥ half of the non-blank lines occur in the current file | 291 | 48% |
| Absent — < half occur | 173 | 28% |
| Stale — matches the file before the agent's own earlier edit | 143 | 24% |
| Escape — matches after undoing literal `\n`, `\"`, `\t` | 1 | 0% |

Success by `old_string` length: 25% (1 line), 21% (2–3), 15% (4–8), 10% (9+). Calls containing a quote fail 84%, others 62%.

## Single-task trials

- E1: the model put the file being edited into the script-path argument in all 10 calls. E2: it overwrote a 400-line module with 2 lines via `write_file`. E3: it used `sed 's/…/…/'` instead of the given template and guessed line numbers, deleting wrong lines.
- F1: the editor sub-agent answered "DONE" after 136 s; the patch was empty.

## Condition K (forgiving matcher)

When `old_string` is not found, the matcher replaces the line window with the highest mean line similarity (≥ 0.85, and ≥ 0.05 above the next window).

- Offline replay predicted 25% of failures would land; it counted repeated retries of the same failing call. Replaying with landed edits applied (`cross.py`) matches the live runs exactly.
- Live (r1 + r3): 10 of 106 "not found" failures landed (9%). Without them edit failure would be 88% and 75%; the matcher's effect (5–6 points) is below H's run-to-run spread (11 points).
- Of 6 forgiving landings in files that parsed, 4 left them unparseable (1 because the window was shifted by a line). Resolved stayed 0.

## Repeats and distinct failures (`distinct.py`, `why_drift.py`)

A repeat is a failed edit call with the same task, file and `old_string` as an earlier failed call.
Across 15 runs, 1,169 of 1,584 failed edit calls (74%) are repeats.

| Cond. | Edit fail, logged | Edit fail, distinct (repeats removed) |
|---|---|---|
| A, D (28 tasks) | 89%, 89% | 63%, 66% |
| D (2 runs) | 90%, 85% | 66%, 62% |
| B (2 runs) | 87%, 89% | 58%, 71% |
| C | 81% | 50% |
| G | 79% | 54% |
| H (3 runs) | 87%, 90%, 79% | 64%, 70%, 59% |
| I | 88% | 70% |
| J | 91% | 72% |
| K (2 runs) | 82%, 70% | 59%, 37% |

129 distinct "not found" failures in `pair_A`, `pair_D`, `sk_D_r2`, `sk_B_r1`, `sk_C_r1`: stale 33 (26%), altered 76 (59%), absent 20 (15%).
Of the 206 wrong lines in altered/absent failures: 34% also appear in `new_string` (intended code written as old code),
29% are ≥ 0.8 similar to a real line (miscopies), 37% neither.
The forgiving matcher would land 41% of distinct altered, 33% of stale and 15% of absent failures.
Live, K landed 10 of 38 distinct inexact edits (26%).
