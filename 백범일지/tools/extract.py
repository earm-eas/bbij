#!/usr/bin/env python3
"""Extract the EPUB into a neutral JSON IR (blocks + runs).

Only the standard library is used.  The source XHTML is well-formed apart
from the HTML entity ``&nbsp;``, which we normalise before parsing.
"""
import json
import os
import re
import sys
import xml.etree.ElementTree as ET

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.environ.get("EPUB_DIR", "/tmp/opencode/epub")
OEBPS = os.path.join(SRC, "OEBPS")

NS = "{http://www.w3.org/1999/xhtml}"


def strip_ns(tag):
    return tag.rsplit("}", 1)[-1]


def read(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read().replace("&nbsp;", "&#160;")


def parse(path):
    return ET.fromstring(read(path))


def classes(el):
    return el.get("class", "").split()


def norm(text):
    return re.sub(r"[ \t\r\n]+", " ", text)


def text_of(el):
    return norm("".join(el.itertext())).strip()


def plain_text(el):
    """Text of an element with footnote markers removed."""
    parts = []

    def visit(node):
        if node.text:
            parts.append(node.text)
        for child in node:
            if strip_ns(child.tag) == "span" and "superior" in classes(child):
                pass
            else:
                visit(child)
            if child.tail:
                parts.append(child.tail)

    visit(el)
    return norm("".join(parts)).strip()


# ---------------------------------------------------------------- metadata
def load_opf():
    opf = parse(os.path.join(OEBPS, "content.opf"))
    meta = {}
    for el in opf.iter():
        name = strip_ns(el.tag)
        if name == "identifier" and el.get("id") == "BookId":
            meta["uuid"] = (el.text or "").strip()
        elif name == "title":
            meta.setdefault("title", (el.text or "").strip())
        elif name == "creator":
            meta.setdefault("creator", (el.text or "").strip())
        elif name == "publisher":
            meta.setdefault("publisher", (el.text or "").strip())
        elif name == "language":
            meta.setdefault("language", (el.text or "").strip())
    for el in opf.iter():
        if strip_ns(el.tag) == "identifier" and el.get("scheme") == "ISBN":
            meta.setdefault("isbn", (el.text or "").strip())
    manifest = {}
    for el in opf.iter():
        if strip_ns(el.tag) == "item":
            manifest[el.get("id")] = {
                "href": el.get("href"),
                "type": el.get("media-type"),
            }
    spine = []
    for el in opf.iter():
        if strip_ns(el.tag) == "itemref":
            spine.append(el.get("idref"))
    return meta, manifest, spine


# ---------------------------------------------------------------- inline
def clean_run(run):
    run = dict(run)
    if "v" in run:
        run["v"] = norm(run["v"])
    return run


def merge_runs(runs):
    out = []
    for run in runs:
        if not run:
            continue
        if run.get("t") == "text" and not run.get("v"):
            continue
        if out and out[-1].get("t") == "text" and run.get("t") == "text":
            a, b = out[-1], run
            style = {k: v for k, v in a.items() if k not in ("t", "v")}
            style2 = {k: v for k, v in b.items() if k not in ("t", "v")}
            if style == style2:
                a["v"] += b["v"]
                continue
        out.append(run)
    for run in out:
        if "v" in run:
            run["v"] = re.sub(r"^ +", " ", run["v"])
    if out:
        if "v" in out[0]:
            out[0]["v"] = out[0]["v"].lstrip()
        if "v" in out[-1]:
            out[-1]["v"] = out[-1]["v"].rstrip()
    return [r for r in out if r.get("t") != "text" or r.get("v")]


def img_src(src):
    return "images/" + src.rsplit("/", 1)[-1]


def span_style(cls):
    style = {}
    for c in cls:
        if c in ("bold_txt", "bold", "MjB", "GoB"):
            style["bold"] = True
            style["family"] = "go" if c in ("bold_txt", "bold", "GoB") else "mj"
        elif c in ("MjM",):
            style["family"] = "mj"
        elif c in ("GoM", "GoL"):
            style["family"] = "go"
        elif c in ("MjL",):
            style["family"] = "mj"
        elif c == "italic":
            style["italic"] = True
        elif c in ("f14", "f12", "f11", "f09", "f08"):
            style["size"] = {"f14": 1.4, "f12": 1.2, "f11": 1.1, "f09": 0.9, "f08": 0.8}[c]
        elif c in ("txt_s",):
            style["size"] = 0.9
        elif c in ("bottom_txt",):
            style["size"] = 0.8
        elif c == "word_b":
            style["word_b"] = True
    return style


def inline_runs(el, footnotes=None):
    runs = []
    if el.text:
        runs.append({"t": "text", "v": el.text})
    for child in el:
        tag = strip_ns(child.tag)
        if tag == "span":
            cls = classes(child)
            style = span_style(cls)
            if "superior" in cls:
                label = text_of(child)
                runs.append({"t": "fn", "label": label, "note": None})
            else:
                sub = inline_runs(child, footnotes)
                for run in sub:
                    if run.get("t") == "text":
                        run.update(style)
                runs.extend(sub)
        elif tag == "img":
            src = img_src(child.get("src", ""))
            cls = classes(child)
            runs.append({"t": "img", "src": src, "cls": cls})
        elif tag == "a":
            runs.extend(inline_runs(child, footnotes))
        elif tag == "br":
            runs.append({"t": "br"})
        else:
            runs.extend(inline_runs(child, footnotes))
        if child.tail:
            runs.append({"t": "text", "v": child.tail})
    return merge_runs(runs)


# ---------------------------------------------------------------- footnotes
LABEL_RE = re.compile(r"^\s*(\d+\)|❇)\s*")


def split_note(el):
    runs = inline_runs(el)
    label = None
    if runs and runs[0].get("t") == "text":
        m = LABEL_RE.match(runs[0]["v"])
        if m:
            label = m.group(1)
            runs[0]["v"] = runs[0]["v"][m.end():]
            runs = merge_runs(runs)
    return label, runs


# ---------------------------------------------------------------- blocks
def is_empty(el):
    return text_of(el) in ("", "\xa0", " ") and el.find(f".//{NS}img") is None \
        and el.find(f".//{NS}span") is None


SIZE_BY_KEY = {"f14": 1.4, "f12": 1.2, "f11": 1.1, "f09": 0.9, "f08": 0.8}


def para_block(el, kind="p"):
    cls = classes(el)
    runs = inline_runs(el)
    if not runs:
        return None
    block = {"t": "p", "runs": runs, "cls": cls}
    if "right" in cls:
        block["align"] = "right"
    elif "center" in cls:
        block["align"] = "center"
    elif "left" in cls:
        block["align"] = "left"
    if "title" in cls:
        block["style"] = "title"
    if "slogan" in cls:
        block["style"] = "slogan"
    if "in0" in cls:
        block["indent"] = 0.0
    if "txt_in" in cls:
        block["inset"] = 1.2
        block["indent"] = 0.0
    elif "ml" in cls:
        block["inset"] = 2.5
        block["indent"] = 0.0
        block["size"] = 0.9
    elif "qu" in cls:
        block["inset"] = 2.0
        block["indent"] = 0.0
        block["size"] = 0.9
    for c in cls:
        if c in SIZE_BY_KEY:
            block["size"] = SIZE_BY_KEY[c]
    return block


def iter_children(el):
    return [c for c in el if strip_ns(c.tag) in ("p", "div", "h1", "h2", "h3")]


def extract_file(relpath):
    tree = parse(os.path.join(OEBPS, relpath))
    body = None
    for el in tree.iter():
        if strip_ns(el.tag) == "body":
            body = el
            break
    assert body is not None, relpath

    children = list(body)
    heading_texts = set()
    for el in children:
        if strip_ns(el.tag) in ("h1", "h2", "h3"):
            heading_texts.add(plain_text(el))

    blocks = []
    heading_blocks = {}
    notes = []          # (label, runs)
    markers = []        # runs referencing marker index
    pending = []        # footnote markers taken out of headings
    # first pass: collect notes.  Most notes carry class="fn_txt", but the
    # source has at least one plain <p> after the footnote separator.
    after_sep = False
    for el in body.iter():
        if strip_ns(el.tag) != "p":
            continue
        cls = classes(el)
        if "footnote" in cls:
            after_sep = True
            continue
        if "fn_txt" in cls or (after_sep and LABEL_RE.match(text_of(el))):
            label, runs = split_note(el)
            notes.append({"label": label, "runs": runs})

    def block_run_lists(block):
        t = block["t"]
        if t in ("p", "listitem"):
            return [block["runs"]]
        if t == "heading":
            return [block.get("runs") or []]
        if t == "list":
            return [i["runs"] for i in block["items"]]
        if t == "figure":
            return [block["caption"]] if block.get("caption") else []
        if t == "chron":
            out = []
            for e in block["entries"]:
                out.append(e["main"])
                out.extend(e["events"])
            return out
        return []

    def pending_target(block):
        t = block["t"]
        if t in ("p", "listitem"):
            return block["runs"]
        if t == "list":
            return block["items"][0]["runs"] if block["items"] else None
        if t == "figure":
            if block.get("caption") is None:
                block["caption"] = []
            return block["caption"]
        if t == "chron":
            return block["entries"][0]["main"] if block["entries"] else None
        return None

    def finish(block):
        if pending:
            target = pending_target(block)
            if target is not None:
                target.extend(pending)
                pending.clear()
        blocks.append(block)

    def emit(el):
        tag = strip_ns(el.tag)
        cls = classes(el)
        if tag in ("h1", "h2", "h3"):
            level = {"h1": 1, "h2": 2, "h3": 3}[tag]
            text = plain_text(el)
            if not text:
                return
            runs = []
            for run in inline_runs(el):
                if run.get("t") == "fn":
                    pending.append(run)
                else:
                    runs.append(run)
            block = {"t": "heading", "level": level, "text": text,
                     "runs": runs, "id": el.get("id")}
            blocks.append(block)
            heading_blocks.setdefault(text, block)
            return
        if tag == "div":
            if "img_center" in cls:
                imgs = [c for c in el.iter() if strip_ns(c.tag) == "img"]
                caps = [c for c in el if strip_ns(c.tag) == "p"]
                src = img_src(imgs[0].get("src", "")) if imgs else None
                cap = None
                if caps:
                    cap = []
                    for i, c in enumerate(caps):
                        if i:
                            cap.append({"t": "br"})
                        cap.extend(inline_runs(c))
                if src:
                    finish({"t": "figure", "src": src, "caption": cap,
                            "full": False})
                return
            if "y_box" in cls:
                entries = []
                cur = None
                for c in el:
                    ctag = strip_ns(c.tag)
                    if ctag != "p":
                        continue
                    ccls = classes(c)
                    if "y_txt_in" in ccls:
                        cur = {"main": inline_runs(c), "events": []}
                        entries.append(cur)
                    elif "ml" in ccls and cur is not None:
                        cur["events"].append(inline_runs(c))
                finish({"t": "chron", "entries": entries})
                return
            for c in el:
                if strip_ns(c.tag) in ("p", "h1", "h2", "h3", "div"):
                    emit(c)
            return
        if tag == "p":
            if "fn_txt" in cls or "footnote" in cls:
                return
            if after_sep and LABEL_RE.match(text_of(el)):
                return
            if is_empty(el):
                return
            key = plain_text(el)
            if ("title" in cls or "center" in cls) and key in heading_blocks:
                # The ebook repeats the (hidden) heading as a visible paragraph.
                # Move any footnote markers to the next paragraph so that they
                # do not leak into the automatically generated table of contents.
                for run in inline_runs(el):
                    if run.get("t") == "fn":
                        pending.append(run)
                return
            if "num_in" in cls or "qu_num" in cls or "dot_in" in cls:
                runs = inline_runs(el)
                m = None
                if runs and runs[0].get("t") == "text":
                    m = re.match(r"^\s*(\d+\.)\s*", runs[0]["v"])
                num = None
                if m:
                    num = m.group(1)
                    runs[0]["v"] = runs[0]["v"][m.end():]
                    runs = merge_runs(runs)
                block = {"t": "listitem", "runs": runs, "num": num,
                         "cls": cls,
                         "style": "quote" if "qu_num" in cls else "plain"}
                finish(block)
                return
            block = para_block(el)
            if block:
                finish(block)
            return

    for el in children:
        if strip_ns(el.tag) in ("p", "h1", "h2", "h3", "div"):
            emit(el)

    # group consecutive listitems
    grouped = []
    for b in blocks:
        if b["t"] == "listitem":
            if grouped and grouped[-1]["t"] == "list":
                grouped[-1]["items"].append(b)
            else:
                grouped.append({"t": "list", "items": [b]})
        else:
            grouped.append(b)
    blocks = grouped

    # pair footnotes by label
    by_label = {}
    for note in notes:
        if note["label"] is not None and note["label"] not in by_label:
            by_label[note["label"]] = note["runs"]
    used = set()
    dangling = 0
    for b in blocks:
        for runs in block_run_lists(b):
            for run in runs:
                if run.get("t") == "fn":
                    label = run["label"]
                    if label in by_label and label not in used:
                        run["note"] = by_label[label]
                        used.add(label)
                    else:
                        dangling += 1
                        run["note"] = None
                        run["plain"] = True

    # A few footnote numbers are plain text rather than <span class="superior">.
    # Recover them when their note exists but no marker was found.
    for note in notes:
        label = note["label"]
        if not label or label in used:
            continue
        found = False
        for b in blocks:
            for runs in block_run_lists(b):
                for i, run in enumerate(runs):
                    if run.get("t") != "text":
                        continue
                    v = run.get("v", "")
                    pos = v.find(label)
                    while pos >= 0:
                        before, after = v[:pos], v[pos + len(label):]
                        if (not before or not before[-1].isdigit()) and \
                           (not after or after[0] in " \t\n\"'“‘"):
                            replacement = []
                            if before:
                                replacement.append({**run, "v": before})
                            replacement.append({"t": "fn", "label": label,
                                                "v": label,
                                                "note": note["runs"]})
                            if after:
                                replacement.append({**run, "v": after})
                            runs[i:i + 1] = replacement
                            used.add(label)
                            found = True
                            break
                        pos = v.find(label, pos + 1)
                    if found:
                        break
                if found:
                    break
            if found:
                break

    dangling = sum(1 for b in blocks for r in walk_runs(b)
                   if r.get("t") == "fn" and r.get("note") is None)
    orphans = [{"label": n["label"], "runs": n["runs"]}
               for n in notes if n["label"] not in used]
    if pending:
        blocks.append({"t": "p", "runs": pending, "cls": []})
    return {
        "file": relpath,
        "blocks": blocks,
        "orphans": orphans,
        "stats": {"markers": sum(1 for b in blocks for r in walk_runs(b)
                                  if r.get("t") == "fn"),
                  "notes": len(notes), "dangling": dangling,
                  "orphans": len(orphans)},
    }


def walk_runs(block):
    if block["t"] in ("p", "listitem", "heading"):
        yield from (block.get("runs") or [])
    elif block["t"] == "list":
        for i in block["items"]:
            yield from i["runs"]
    elif block["t"] == "figure" and block.get("caption"):
        yield from block["caption"]
    elif block["t"] == "chron":
        for e in block["entries"]:
            yield from e["main"]
            for ev in e["events"]:
                yield from ev


def main():
    meta, manifest, spine = load_opf()
    files = []
    report = []
    for idref in spine:
        item = manifest[idref]
        if item["type"] != "application/xhtml+xml":
            continue
        data = extract_file(item["href"])
        data["id"] = idref
        files.append(data)
        st = data["stats"]
        report.append((idref, st["markers"], st["notes"], st["dangling"],
                       st["orphans"]))
    ir = {"meta": meta, "files": files}
    out = os.path.join(ROOT, "tools", "ir.json")
    with open(out, "w", encoding="utf-8") as fh:
        json.dump(ir, fh, ensure_ascii=False, indent=1)
    print(f"wrote {out}")
    print(f"{'file':22} {'mark':>4} {'note':>4} {'dang':>4} {'orph':>4}")
    for row in report:
        print(f"{row[0]:22} {row[1]:4} {row[2]:4} {row[3]:4} {row[4]:4}")


if __name__ == "__main__":
    main()
