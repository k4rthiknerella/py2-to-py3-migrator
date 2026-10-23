#!/bin/sh
# What each real interpreter makes of tests/py3_cases.py: see py3_verdicts.py.
# Usage: sh .py-migrate/py3_verdicts.sh OUT    (OUT under this repository)
set -eu
REPO=$(cd "$(dirname "$0")/.." && pwd)
OUT=$1
mkdir -p "$OUT"
REL=$(cd "$OUT" && pwd | sed "s|^$REPO/||")
python3 "$REPO/.py-migrate/py3_verdicts.py" dump "$OUT/cases.json"
run() {
    docker run --rm -m 1g --memory-swap 1g --user 1000 -e HOME=/tmp -e PYTHONDONTWRITEBYTECODE=1 \
        -v "$REPO:/src" -w /src "python:$1-slim" python .py-migrate/compile3_oracle.py $2 cases "$REL/cases.json" "$REL/$1.jsonl"
}
run 2.7.18 --ast
for v in 3.6.15 3.7.17 3.8.20 3.9.25 3.10.19 3.11.14 3.12.12 3.13.12 3.14.9 3.15.1; do
    run "$v" ""
done
python3 "$REPO/.py-migrate/py3_verdicts.py" merge "$OUT" "$REPO/tests/data/py3_verdicts.json"
