#!/bin/sh
# The facts .py-migrate/py3_data.py probes, from each judged interpreter in turn.
set -eu
REPO=$(cd "$(dirname "$0")/.." && pwd)
OUT=$1
mkdir -p "$OUT"
REL=$(cd "$OUT" && pwd | sed "s|^$REPO/||")
for v in 3.6.15 3.7.17 3.8.20 3.9.25 3.10.19 3.11.14 3.12.12 3.13.12 3.14.9 3.15.1; do
    docker run --rm -m 1g --memory-swap 1g --user 1000 -e HOME=/tmp -e PYTHONDONTWRITEBYTECODE=1 \
        -v "$REPO:/src" -w /src "python:$v-slim" \
        python .py-migrate/py3_data.py probe .py-migrate/NameAliases-17.0.0.txt "$REL/$v.json"
done
