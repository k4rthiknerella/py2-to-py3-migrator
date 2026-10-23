# -*- coding: utf-8 -*-
import os
import shutil
import tempfile

from py2scan.scanner import scan


def make_tree(n):
    root = tempfile.mkdtemp()
    for i in range(n):
        with open(os.path.join(root, "m%02d.py" % i), "wb") as f:
            if i % 2 == 0:
                f.write(b"print 'x'\n")
            else:
                f.write(b"x = 1\n")
    return root


def test_output_identical_across_job_counts():
    root = make_tree(12)
    try:
        baseline = scan(root, jobs=1)
        for jobs in (1, 2, 4, 8):
            files, findings = scan(root, jobs=jobs)
            assert files == baseline[0]
            assert [f.to_dict() for f in findings] == [f.to_dict() for f in baseline[1]]
    finally:
        shutil.rmtree(root)
