#!/bin/bash
# Skill experiment: runs PLAN entries "COND:REP" in order on the eval split, same limits as pair.sh.
# Usage: PLAN="B:1 C:1 D:2 ..." TASKS_FILE=eval13.txt bash skill_runs.sh
SRC=${SRC:?set SRC to the folder holding agent_configs/ and data/tasks.jsonl}
TOOLS=$(cd "$(dirname "$0")" && pwd)
TASKS=$(tr -d '\r' < $TOOLS/${TASKS_FILE:-eval13.txt})
cd ${WORK:-~/gemma4} && . venv/bin/activate
# 11-02 15:00 one task filled WSL RAM + swap. Cap each process's address space; a runaway task fails alone.
ulimit -v 6000000
for P in $PLAN; do
  COND=${P%%:*}; REP=${P##*:}; OUT=run/sk_${COND}_r$REP
  [ -f $OUT/summary.json ] && [ "$(python3 -c "import json;print(json.load(open('$OUT/summary.json'))['total_tasks'])")" = "$(echo $TASKS | wc -w)" ] && continue
  rm -rf run/sub $OUT
  cp -r $SRC/agent_configs/condition_$COND run/sub
  cp $TOOLS/eval_config.yaml run/sub/
  python $TOOLS/run_eval.py eval --tasks $SRC/data/tasks.jsonl --snapshots-dir run/snapshots \
    --submission-dir run/sub --results-dir $OUT --sandbox subprocess --models-yaml run/models.yaml \
    --task-ids $TASKS --max-tool-calls 30 --max-time-minutes 7 --max-turns 60 --display quiet 2>&1 | tail -3 | cut -c1-200
  echo "done $P $(date)"
done
touch $TOOLS/skill_runs.${DONE_TAG:-done}
