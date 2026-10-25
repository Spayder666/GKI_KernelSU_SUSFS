#!/usr/bin/env python3
"""Drop the blk.h context line from an android14-6.1 SUSFS namespace.c hunk.

6.1 sublevels below 157 do not ship include/trace/hooks/blk.h. The SUSFS
base patch still lists `#include <trace/hooks/blk.h>` as context in
fs/namespace.c, so patch rejects that hunk (6.1.145: "Hunk #1 FAILED at 32").
Inserting the include into the tree fails the build because the header is
absent. Remove the context line and shrink the hunk that contained it.

Only a unified-diff context line (one leading space) inside fs/namespace.c
is removed. Other files and added/removed lines are left alone. A missing
line is not an error: a future SUSFS tip may already have dropped it.
"""

import re
import sys

CONTEXT = " #include <trace/hooks/blk.h>\n"
HUNK_RE = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@(.*\n)$")
NS_PREFIX = "+++ b/fs/namespace.c"


def _in_namespace(line, state):
    if line.startswith("diff --git "):
        return False
    if line.startswith(NS_PREFIX) and (
        len(line) == len(NS_PREFIX) or line[len(NS_PREFIX)] in "\t\n"
    ):
        return True
    if line.startswith("--- a/") or line.startswith("+++ b/"):
        return False
    return state


def _adjust_header(header, dropped):
    match = HUNK_RE.match(header)
    if not match:
        sys.exit(
            "susfs base patch: namespace.c hunk header not parseable: %r" % header
        )
    old_start, old_count, new_start, new_count, tail = match.groups()
    old_n = int(old_count) if old_count is not None else 1
    new_n = int(new_count) if new_count is not None else 1
    old_n -= dropped
    new_n -= dropped
    if old_n < 1 or new_n < 1:
        sys.exit(
            "susfs base patch: dropping blk.h context would empty a namespace.c hunk"
        )
    return "@@ -%s,%d +%s,%d @@%s" % (old_start, old_n, new_start, new_n, tail)


def rewrite(text):
    lines = text.splitlines(keepends=True)
    out = []
    in_ns = False
    dropped_total = 0
    index = 0
    while index < len(lines):
        line = lines[index]
        in_ns = _in_namespace(line, in_ns)
        if in_ns and line.startswith("@@"):
            hunk = [line]
            index += 1
            while index < len(lines):
                nxt = lines[index]
                if (
                    nxt.startswith("@@")
                    or nxt.startswith("diff --git ")
                    or nxt.startswith("--- a/")
                    or nxt.startswith("+++ b/")
                ):
                    break
                hunk.append(nxt)
                index += 1
            kept = []
            dropped = 0
            for entry in hunk[1:]:
                if entry == CONTEXT:
                    dropped += 1
                    continue
                kept.append(entry)
            header = hunk[0]
            if dropped:
                header = _adjust_header(header, dropped)
                dropped_total += dropped
            out.append(header)
            out.extend(kept)
            continue
        out.append(line)
        index += 1
    return "".join(out), dropped_total


def main(path):
    with open(path, encoding="utf-8") as handle:
        text = handle.read()
    updated, dropped = rewrite(text)
    if dropped == 0:
        print("susfs base patch: namespace.c blk.h context line not present")
        return
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(updated)
    print(
        "susfs base patch: dropped %d namespace.c blk.h context line(s) "
        "and adjusted hunk headers" % dropped
    )


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit("usage: susfs_drop_blk_context.py <patch>")
    main(sys.argv[1])
