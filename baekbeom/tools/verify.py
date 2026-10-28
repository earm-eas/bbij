#!/usr/bin/env python3
"""Consistency checks between the source EPUB, the IR and the Typst output."""
import collections
import json
import os
import re
import sys
import xml.etree.ElementTree as ET

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import extract  # noqa: E402

IR = os.path.join(HERE, "ir.json")
EPUB = os.environ.get("EPUB_DIR", "/tmp/opencode/epub")
OEBPS = os.path.join(EPUB, "OEBPS")


def walk_text(block):
    out = []

    def add(runs):
        for r in runs:
            if r.get("t") == "text":
                out.append(r.get("v", ""))
            elif r.get("t") == "fn":
                if r.get("v"):
                    out.append(r["v"])
                if r.get("note"):
                    add(r["note"])

    t = block["t"]
    if t == "heading":
        add(block["runs"])
    elif t == "p":
        add(block["runs"])
    elif t == "list":
        for i in block["items"]:
            if i.get("num"):
                out.append(i["num"])
            add(i["runs"])
    elif t == "figure" and block.get("caption"):
        add(block["caption"])
    elif t == "chron":
        for e in block["entries"]:
            add(e["main"])
            for ev in e["events"]:
                add(ev)
    return out


def image_refs(block):
    refs = []

    def add(runs):
        for r in runs:
            if r.get("t") == "img":
                refs.append(r["src"])

    t = block["t"]
    if t == "heading":
        add(block["runs"])
    elif t == "p":
        add(block["runs"])
    elif t == "list":
        for i in block["items"]:
            add(i["runs"])
    elif t == "figure":
        refs.append(block["src"])
        if block.get("caption"):
            add(block["caption"])
    elif t == "chron":
        for e in block["entries"]:
            add(e["main"])
            for ev in e["events"]:
                add(ev)
    return refs


def source_text(relpath):
    tree = extract.parse(os.path.join(OEBPS, relpath))
    body = next(el for el in tree.iter() if extract.strip_ns(el.tag) == "body")
    heading_texts = set()
    for el in body:
        if extract.strip_ns(el.tag) in ("h1", "h2", "h3"):
            heading_texts.add(extract.plain_text(el))
    parts = []

    def visit_text(node):
        if node.text:
            parts.append(node.text)
        for child in node:
            if extract.strip_ns(child.tag) == "span" and "superior" in extract.classes(child):
                pass
            else:
                visit_text(child)
            if child.tail:
                parts.append(child.tail)

    after_sep = False
    for el in body.iter():
        tag = extract.strip_ns(el.tag)
        if tag in ("h1", "h2", "h3"):
            visit_text(el)
        elif tag == "p":
            cls = extract.classes(el)
            if "footnote" in cls:
                after_sep = True
                continue
            if "fn_txt" in cls or (after_sep and extract.LABEL_RE.match(
                    extract.text_of(el))):
                text = "".join(el.itertext())
                text = re.sub(r"^\s*(\d+\)|❇)\s*", "", text)
                parts.append(text)
                continue
            if extract.is_empty(el):
                continue
            key = extract.plain_text(el)
            if ("title" in cls or "center" in cls) and key in heading_texts:
                continue
            visit_text(el)
    return "".join(parts)


def main():
    ir = json.load(open(IR, encoding="utf-8"))
    problems = []
    missing_images = set()
    stats = {"markers": 0, "notes": 0, "dangling": 0, "orphans": 0}
    for f in ir["files"]:
        stats["markers"] += f["stats"]["markers"]
        stats["notes"] += f["stats"]["notes"]
        stats["dangling"] += f["stats"]["dangling"]
        stats["orphans"] += f["stats"]["orphans"]
        ir_parts = []
        for b in f["blocks"]:
            ir_parts += walk_text(b)
            for src in image_refs(b):
                if not os.path.exists(os.path.join(ROOT, src)):
                    missing_images.add(src)
        for o in f.get("orphans", []):
            ir_parts += [r.get("v", "") for r in o["runs"] if r.get("t") == "text"]
        src = source_text(f["file"])
        a = re.sub(r"\s+", "", "".join(ir_parts))
        b = re.sub(r"\s+", "", src)
        if collections.Counter(a) != collections.Counter(b):
            i = next((i for i, (x, y) in enumerate(zip(a, b)) if x != y), min(len(a), len(b)))
            problems.append((f["id"], len(a), len(b), a[max(0, i - 25):i + 25],
                             b[max(0, i - 25):i + 25]))

    print("footnotes: %d markers / %d notes, %d dangling, %d orphan notes"
          % (stats["markers"], stats["notes"], stats["dangling"], stats["orphans"]))
    if missing_images:
        print("MISSING IMAGES:", sorted(missing_images))
    if problems:
        print("TEXT MISMATCH in %d files:" % len(problems))
        for pid, la, lb, ca, cb in problems:
            print("  %-22s ir=%d src=%d\n    ir : %r\n    src: %r" % (pid, la, lb, ca, cb))
        return 1
    print("text conservation: OK (%d files)" % len(ir["files"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
