import os, sys, warnings
out = getattr(sys.stdout, "buffer", sys.stdout)
def say(s):
    out.write((s + u"\n").encode("utf-8", "replace"))
checked = bad = 0
skipped = []
for raw in open(sys.argv[1], "rb").read().split(b"\0"):
    if not raw or os.path.isdir(raw):
        continue
    name = raw.decode("utf-8", "replace")
    try:
        src = open(raw, "rb").read()
    except (IOError, OSError):
        skipped.append(name)
        continue
    if not name.endswith(u".py") and not (src[:2] == b"#!" and b"python" in src.split(b"\n", 1)[0]):
        continue
    checked += 1
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        try:
            compile(src, raw if str is bytes else name, "exec", 0, True)
        except Exception as e:
            bad += 1
            say(u"%s:%s: %s: %s" % (name, getattr(e, "lineno", None) or 0, type(e).__name__, getattr(e, "msg", e)))
    for w in caught:
        say(u"%s:%s: %s: %s" % (name, w.lineno, w.category.__name__, w.message))
for name in skipped:
    say(u"%s:0: Unreadable" % name)
sys.stderr.write("checked %d, failed %d, unreadable %d\n" % (checked, bad, len(skipped)))
sys.exit(1 if bad or skipped or not checked else 0)
