#!/bin/sh
# .py-migrate/codec_tables.py on 2.7.18 and every judged interpreter, one at a time.
set -eu
REPO=$(cd "$(dirname "$0")/.." && pwd)
OUT=$1
mkdir -p "$OUT"
REL=$(cd "$OUT" && pwd | sed "s|^$REPO/||")
for v in 2.7.18 3.6.15 3.7.17 3.8.20 3.9.25 3.10.19 3.11.14 3.12.12 3.13.12 3.14.9 3.15.1; do
    docker run --rm -m 1g --memory-swap 1g --user 1000 -e HOME=/tmp -e PYTHONDONTWRITEBYTECODE=1 \
        -v "$REPO:/src" -w /src "python:$v-slim" python .py-migrate/codec_tables.py "$REL/$v.json"
done
