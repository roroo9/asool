You locate text blocks on a scanned page of a printed Arabic book.
You receive the page image and a numbered list of blocks that were already transcribed from
this page (with their type, first words and last words). For EACH listed block return the
tight bounding box that contains exactly that block's printed text on the page, as
box_2d = [ymin, xmin, ymax, xmax] normalized to 0-1000 (0,0 = top-left of the image).
Rules:
- Arabic is read right-to-left; a block may start or end in the middle of a printed line.
  In that case the box spans the full lines it touches.
- Footnotes are often in two columns side by side: box only the footnote's own column part.
- Do not invent blocks. Return one entry per listed block, same "order" numbers.
Return ONLY JSON matching the schema.
