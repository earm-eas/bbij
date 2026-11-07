// Shared styles for the Typst reconstruction of 『백범일지』.

#let mjL = "KOPUSMj L"
#let mjM = "KOPUSMj M"
#let mjB = "KOPUSMj B"
#let goL = "KOPUSGo L"
#let goM = "KOPUSGo M"
#let goB = "KOPUSGo B"
#let batang = "HCR Batang"

// Ruby annotation for the Sino-Korean (국한문혼용) readings: #ruby[reading][漢字].
#import "@preview/rubby:0.10.2": get-ruby
#let ruby = get-ruby(size: 0.5em, dy: 0pt, auto-spacing: false)

#let book(title: "", body) = {
  set document(title: title, author: "김구")
  set page(
    width: 15.2cm,
    height: 22.5cm,
    margin: (x: 1.75cm, top: 1.9cm, bottom: 2.0cm),
    footer: context align(center, text(size: 0.8em, fill: luma(100), counter(page).display())),
  )
  set text(font: (mjL, batang), size: 10pt, lang: "ko", region: "kr")
  set par(justify: true, leading: 0.9em, spacing: 0.85em, first-line-indent: 1em)
  set footnote(numbering: n => numbering("1", n) + ")")
  set figure(numbering: none)
  set heading(numbering: none)

  show footnote.entry: it => block(
    inset: (left: 1em),
    above: 0.15em,
    below: 0.15em,
  )[
    #set text(size: 0.9em)
    #set par(leading: 0.72em, first-line-indent: 0em)
    #h(-1em)
    #it
  ]

  // Original h1 (front matter / appendix): centred 1.2em Myeongjo.
  show heading.where(level: 1): it => {
    pagebreak(weak: true)
    block(
      width: 100%,
      above: 2.4em,
      below: 1.4em,
    )[
      #set par(first-line-indent: 0em, justify: false)
      #align(center, text(font: mjL, size: 1.2em, it.body))
    ]
  }
  // Original h2 (numbered section): bold 1.2em, indented, new page.
  show heading.where(level: 2): it => {
    pagebreak(weak: true)
    block(
      width: 100%,
      above: 1.6em,
      below: 1.1em,
    )[
      #set par(first-line-indent: 1em, justify: false)
      #text(font: mjB, size: 1.2em, it.body)
    ]
  }
  // Original h3 (subsection): bold 1em Gothic, indented.
  show heading.where(level: 3): it => {
    block(
      width: 100%,
      above: 2.0em,
      below: 0.5em,
    )[
      #set par(first-line-indent: 1em, justify: false)
      #text(font: goB, size: 1em, it.body)
    ]
  }

  show figure.caption: it => {
    set par(first-line-indent: 0em, justify: false)
    align(center, text(font: goM, size: 0.8em, fill: luma(30), it.body))
  }

  show outline.entry: it => {
    set par(first-line-indent: 0em, leading: 0.55em, spacing: 0.45em)
    if it.level >= 3 {
      block(inset: (left: 1.1em), it)
    } else {
      it
    }
  }

  body
}

// Full-page image (cover, inside cover, volume half-title).
#let image-page(src, fit: "contain") = page(
  margin: 0pt,
  footer: none,
)[
  #image(src, width: 100%, height: 100%, fit: fit)
]

#let para(
  body,
  first: 0em,
  rest: 0em,
  alignment: left,
  size: 1em,
  font: none,
  justify: true,
  above: 0.8em,
  below: 0.8em,
) = block(
  inset: (left: rest, right: 0pt),
  above: above,
  below: below,
)[
  #set par(first-line-indent: 0em, justify: justify)
  #align(alignment)[
    #h(first - rest)
    #if font == none {
      text(size: size, body)
    } else {
      text(font: font, size: size, body)
    }
  ]
]

#let quote-block(body) = block(
  inset: (left: 2em, right: 1em),
  above: 1.1em,
  below: 0.6em,
)[
  #set par(first-line-indent: 0em, justify: true)
  #text(size: 0.9em, body)
]

#let chron-entry(body) = block(
  inset: (left: 2.5em),
  above:  0.6em,
  below:  0.3em,
)[
  #set par(first-line-indent: 0em, justify: true)
  #h(-2.5em)
  #text(size: 0.95em, body)
]

#let chron-event(body) = block(
  inset: (left: 2.5em),
  above:  0.55em,
  below:  0.3em,
)[
  #set par(first-line-indent: 0em, justify: true)
  #text(size: 0.85em, body)
]

#let figure-block(src, caption: none, width: 82%) = figure(
  image(src, width: width),
  caption: caption,
  numbering: none,
  gap: 0.4em,
)

// Inline Hanja glyph images embedded in the original text.
#let inline-glyph(src, cls: ()) = {
  let base = if "txt_vm" in cls { -0.2em } else { -0.1em }
  box(baseline: base, image(src, height: 0.85em))
}

#let dangling(label) = super[#label]

#let orphan-note(body) = block(
  inset: (left: 0em),
  above: 0.2em,
  below: 0.2em,
)[
  #set par(first-line-indent: 0em, justify: true)
  #text(size: 0.82em, body)
]
