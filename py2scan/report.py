# -*- coding: utf-8 -*-
from collections import Counter


def compute_summary(files, findings):
    if not files:
        return 100.0, {}
    blocker_files = set(f.file for f in findings if f.severity == "blocker")
    clean = len(files) - len(blocker_files)
    readiness = round(100.0 * clean / len(files), 1)
    counts = dict(Counter(f.rule for f in findings))
    return readiness, counts


def to_json(files, findings):
    readiness, rules = compute_summary(files, findings)
    return {
        "files": len(files),
        "readiness": readiness,
        "rules": rules,
        "findings": [f.to_dict() for f in findings],
    }
