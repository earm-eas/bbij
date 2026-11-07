#!/usr/bin/env python3
"""Turn the JSON IR into a Typst project (content/*.typ + main.typ)."""
import json
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONTENT = os.path.join(ROOT, "content")

SPECIAL = {
    "cover.xhtml": ("image", "cover", "cover"),
    "incover.xhtml": ("image", "incover", "contain"),
    "chapter1.xhtml": ("image", "c1", "contain"),
    "chapter2.xhtml": ("image", "c2", "contain"),
}

PLAIN_INDENT = {"author.xhtml", "rights.xhtml", "kpc_dotum_2.xhtml"}


def esc(text):
    text = text.replace("\xa0", "\x00")
    text = text.replace("\\", "\\\\")
    text = re.sub(r"^(\s*\d+)\.", r"\1\\.", text)
    text = re.sub(r"^(\s*)([-+])(\s)", r"\1\\\2\3", text)
    for ch in "#$*_`<>@[]~":
        text = text.replace(ch, "\\" + ch)
    text = text.replace("//", "\\/\\/")
    return text.replace("\x00", "~")


def run_markup(run):
    t = run["t"]
    if t == "text":
        v = esc(run.get("v", ""))
        attrs = []
        if run.get("bold"):
            attrs.append('font: "%s"' % ("KOPUSGo B" if run.get("family") == "go" else "KOPUSMj B"))
        elif run.get("family") == "go":
            attrs.append('font: "KOPUSGo M"')
        elif run.get("family") == "mj":
            attrs.append('font: "KOPUSMj M"')
        if run.get("size"):
            attrs.append("size: %gem" % run["size"])
        if run.get("italic"):
            attrs.append('style: "italic"')
        if attrs:
            return "#text(%s)[%s]" % (", ".join(attrs), v)
        return v
    if t == "fn":
        if run.get("note") is not None:
            label = esc(run.get("label", ""))
            return "#footnote(numbering: _ => [%s])[#h(0.35em)%s]" % (
                label, runs_markup(run["note"]))
        return "#dangling[%s]" % esc(run.get("label", ""))
    if t == "img":
        cls = run.get("cls") or []
        if not cls:
            clstext = "()"
        elif len(cls) == 1:
            clstext = '("%s",)' % cls[0]
        else:
            clstext = "(%s)" % ", ".join('"%s"' % c for c in cls)
        return '#inline-glyph("/images/%s", cls: %s)' % (
            os.path.basename(run["src"]), clstext)
    if t == "br":
        return "#linebreak()"
    return ""


def runs_markup(runs):
    return "".join(run_markup(r) for r in runs)


def emit_list_item(item):
    cls = item.get("cls") or []
    body = runs_markup(item["runs"])
    if item.get("num"):
        body = "#text(font: \"KOPUSMj M\")[%s] %s" % (esc(item["num"]), body)
    if item.get("style") == "quote":
        return "#para(first: 1em, rest: 2em, size: 0.9em)[%s]" % body
    if "dot_in" in cls:
        return "#para(first: 0.3em, rest: 1.5em, size: 0.9em)[%s]" % body
    return "#para(first: 0em, rest: 1.3em)[%s]" % body


def emit_para(b, default_indent=1.0, default_justify=True, default_size=1.0,
              default_font=None):
    cls = b.get("cls") or []
    body = runs_markup(b["runs"])
    if "qu" in cls:
        return "#quote-block[%s]" % body
    indent = b.get("indent", default_indent)
    inset = b.get("inset", 0.0)
    size = b.get("size", default_size)
    alignment = b.get("align", "left")
    first = inset + indent
    rest = inset
    if alignment != "left":
        first = 0.0
        rest = 0.0
    style = b.get("style")
    if style == "title":
        font = 'font: "KOPUSMj B", '
    elif style == "slogan":
        font = 'font: "KOPUSGo B", '
    elif default_font:
        font = 'font: "%s", ' % default_font
    else:
        font = ""
    justify = default_justify and ("word_b" not in cls)
    return "#para(%sfirst: %gem, rest: %gem, alignment: %s, size: %gem, justify: %s)[%s]" % (
        font, first, rest, alignment, size, "true" if justify else "false", body)


def emit_block(b, default_indent, default_justify=True, default_size=1.0,
               default_font=None):
    t = b["t"]
    if t == "heading":
        level = min(b["level"], 3)
        return "#heading(level: %d)[%s]" % (level, runs_markup(b["runs"]))
    if t == "p":
        return emit_para(b, default_indent, default_justify, default_size,
                         default_font)
    if t == "list":
        return "\n".join(emit_list_item(i) for i in b["items"])
    if t == "figure":
        cap = "none"
        if b.get("caption"):
            cap = "[%s]" % runs_markup(b["caption"])
        return '#figure-block("/images/%s", caption: %s)' % (
            os.path.basename(b["src"]), cap)
    if t == "chron":
        out = []
        for e in b["entries"]:
            out.append("#chron-entry[%s]" % runs_markup(e["main"]))
            for ev in e["events"]:
                out.append("#chron-event[%s]" % runs_markup(ev))
        return "\n".join(out)
    return ""


def sanitize(name):
    return re.sub(r"[^A-Za-z0-9_-]", "-", name)


def main():
    ir = json.load(open(os.path.join(ROOT, "tools", "ir.json"), encoding="utf-8"))
    os.makedirs(CONTENT, exist_ok=True)
    for old in os.listdir(CONTENT):
        if old.endswith(".typ"):
            os.unlink(os.path.join(CONTENT, old))

    includes = []
    for index, f in enumerate(ir["files"]):
        fid = f["id"]
        name = "%02d-%s.typ" % (index, sanitize(fid.replace(".xhtml", "")))
        path = os.path.join(CONTENT, name)
        lines = [
            "// generated from %s" % f["file"],
            '#import "/lib.typ": *',
            "#counter(footnote).update(0)",
        ]
        if fid in SPECIAL:
            _, stem, fit = SPECIAL[fid]
            lines = ["// generated from %s" % f["file"],
                     '#import "/lib.typ": *',
                     '#image-page("/images/%s.jpg", fit: "%s")' % (stem, fit)]
        else:
            if fid in ("rights.xhtml", "kpc_dotum_2.xhtml"):
                lines.append("#pagebreak()")
            plain = fid in PLAIN_INDENT
            default_indent = 0.0 if plain else 1.0
            default_size = 0.9 if plain else 1.0
            default_font = "KOPUSGo L" if fid == "kpc_dotum_2.xhtml" else None
            for b in f["blocks"]:
                code = emit_block(b, default_indent, default_justify=not plain,
                                  default_size=default_size,
                                  default_font=default_font)
                if code:
                    lines.append(code)
            if f.get("orphans"):
                lines.append("#v(0.6em)")
                for o in f["orphans"]:
                    label = esc(o["label"] or "")
                    body = runs_markup(o["runs"])
                    lines.append("#orphan-note[#text(font: \"KOPUSMj M\")[%s] %s]" % (label, body))
        with open(path, "w", encoding="utf-8") as fh:
            fh.write("\n".join(lines) + "\n")
        includes.append((fid, name))

    main_lines = [
        "// Reconstructed from the EPUB edition of 『백범일지』.",
        '#import "/lib.typ": *',
        '#show: book.with(title: "백범일지")',
        "",
    ]
    for fid, name in includes:
        main_lines.append('#include "/content/%s"' % name)
        if fid == "inner_txt.xhtml":
            main_lines += [
                "",
                "#pagebreak(weak: true)",
                "#outline(title: [차례], depth: 3, indent: 0pt)",
                "",
            ]
    with open(os.path.join(ROOT, "main.typ"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(main_lines) + "\n")
    print("generated %d content files + main.typ" % len(includes))


if __name__ == "__main__":
    main()
