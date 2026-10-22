"""Conversion du rapport Markdown en PDF, sans modification de la source."""
from pathlib import Path
import hashlib
import html
import json
import re
import sys

sys.dont_write_bytecode = True

from markdown_it import MarkdownIt
import matplotlib
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    BaseDocTemplate, Frame, PageTemplate, Paragraph, Spacer, PageBreak,
    Table, TableStyle, ListFlowable, ListItem, XPreformatted,
)
from reportlab.platypus.tableofcontents import TableOfContents

AUDIT = Path(__file__).resolve().parents[2]
SOURCE = AUDIT / "audit_critique_simulation_2026-10-18.md"
OUTPUT = SOURCE.with_suffix(".pdf")
FONTDIR = Path(matplotlib.get_data_path()) / "fonts" / "ttf"
for name, filename in [
    ("Audit", "DejaVuSans.ttf"), ("Audit-Bold", "DejaVuSans-Bold.ttf"),
    ("Audit-Italic", "DejaVuSans-Oblique.ttf"),
    ("Audit-BoldItalic", "DejaVuSans-BoldOblique.ttf"),
    ("AuditMono", "DejaVuSansMono.ttf"),
]:
    pdfmetrics.registerFont(TTFont(name, str(FONTDIR / filename)))
pdfmetrics.registerFontFamily("Audit", normal="Audit", bold="Audit-Bold",
                             italic="Audit-Italic", boldItalic="Audit-BoldItalic")
pdfmetrics.registerFontFamily("AuditMono", normal="AuditMono", bold="AuditMono",
                             italic="AuditMono", boldItalic="AuditMono")

BLUE = colors.HexColor("#183b59")
INK = colors.HexColor("#202b34")
MUTED = colors.HexColor("#64727d")
LINK = colors.HexColor("#1b628d")
PAGE_W, PAGE_H = A4
MARGIN_X, MARGIN_TOP, MARGIN_BOTTOM = 50, 43, 46
WIDTH = PAGE_W - 2 * MARGIN_X

BODY = ParagraphStyle("Body", fontName="Audit", fontSize=9.5, leading=13.65,
    textColor=INK, alignment=TA_LEFT, spaceAfter=7.8, splitLongWords=True,
    allowWidows=0, allowOrphans=0)
STYLES = {
    "body": BODY,
    "title": ParagraphStyle("Title", parent=BODY, fontName="Audit-Bold",
        fontSize=21, leading=26, textColor=BLUE, spaceAfter=13, keepWithNext=True),
    "meta": ParagraphStyle("Meta", parent=BODY, fontSize=9, leading=13,
        textColor=MUTED, spaceAfter=16),
    "h2": ParagraphStyle("H2", parent=BODY, fontName="Audit-Bold", fontSize=13.4,
        leading=17.6, textColor=BLUE, spaceBefore=15, spaceAfter=8, keepWithNext=True),
    "h3": ParagraphStyle("H3", parent=BODY, fontName="Audit-Bold", fontSize=10.8,
        leading=14.8, spaceBefore=11, spaceAfter=6, keepWithNext=True),
    "callout": ParagraphStyle("Callout", parent=BODY, fontSize=10, leading=14.4,
        spaceAfter=0),
    "cell": ParagraphStyle("Cell", parent=BODY, fontSize=8.15, leading=11.5,
        spaceAfter=0, allowWidows=1, allowOrphans=1),
    "th": ParagraphStyle("TH", parent=BODY, fontName="Audit-Bold", fontSize=8.15,
        leading=11.5, textColor=colors.white, spaceAfter=0, allowWidows=1, allowOrphans=1),
    "code": ParagraphStyle("Code", parent=BODY, fontName="AuditMono", fontSize=7.45,
        leading=10.9, leftIndent=0, spaceBefore=5, spaceAfter=8,
        backColor=colors.HexColor("#f2f5f7"), borderPadding=8),
}


def normalized(text):
    # Normalisation typographique de tirets seulement ; signes mathématiques conservés.
    return re.sub("[\u2010-\u2015]", "-", text).replace("\u00a0", " ").replace("\u202f", " ")


def rich(token):
    parts = []
    for child in token.children or []:
        t, c = child.type, child.content
        if t == "text":
            parts.append(html.escape(normalized(c)))
        elif t == "code_inline":
            parts.append('<font name="AuditMono" size="8.0">' + html.escape(normalized(c)) + '</font>')
        elif t == "strong_open": parts.append("<b>")
        elif t == "strong_close": parts.append("</b>")
        elif t == "em_open": parts.append("<i>")
        elif t == "em_close": parts.append("</i>")
        elif t == "link_open":
            parts.append('<link href="' + html.escape(child.attrGet("href"), quote=True)
                         + '" color="#1b628d"><u>')
        elif t == "link_close": parts.append("</u></link>")
        elif t in ("softbreak", "hardbreak"): parts.append(" " if t == "softbreak" else "<br/>")
        else: raise ValueError(f"Inline non pris en charge : {t}")
    return "".join(parts)


def footer(canvas, doc):
    canvas.saveState()
    canvas.setStrokeColor(colors.HexColor("#dce3e9"))
    canvas.setLineWidth(0.5)
    canvas.line(MARGIN_X, 32, PAGE_W-MARGIN_X, 32)
    canvas.setFont("Audit", 7.2)
    canvas.setFillColor(MUTED)
    canvas.drawString(MARGIN_X, 20, "MicroWaveTomography - Audit du 18 octobre 2026")
    canvas.drawRightString(PAGE_W-MARGIN_X, 20, f"{doc.page}")
    if doc.page > 1:
        canvas.setFont("Audit", 7)
        canvas.drawString(MARGIN_X, PAGE_H-25, "SIMULATEUR ET FICHIERS DE FABRICATION")
    canvas.restoreState()


class AuditDoc(BaseDocTemplate):
    def afterFlowable(self, flowable):
        if getattr(flowable, "audit_heading", None):
            level, title, key = flowable.audit_heading
            self.canv.bookmarkPage(key)
            self.canv.addOutlineEntry(title, key, level=level, closed=False)
            if level == 0:
                self.notify("TOCEntry", (0, title, self.page, key))


def make_table(tokens, index, ordinal):
    rows = []
    row = None
    is_head = False
    while tokens[index].type != "table_close":
        tok = tokens[index]
        if tok.type == "thead_open": is_head = True
        elif tok.type == "thead_close": is_head = False
        elif tok.type == "tr_open": row = []
        elif tok.type == "tr_close": rows.append(row)
        elif tok.type == "inline":
            row.append(Paragraph(rich(tok), STYLES["th" if is_head else "cell"]))
        index += 1
    widths = [
        [.24, .41, .35], [.35, .35, .30], [.16, .39, .29, .16],
        [.52, .26, .22], [.23, .49, .28], [.18, .82],
    ][ordinal]
    assert len(widths) == len(rows[0])
    table = Table(rows, colWidths=[WIDTH*w for w in widths], repeatRows=1,
                  hAlign="LEFT", spaceBefore=3, spaceAfter=11)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,0), BLUE),
        ("VALIGN", (0,0), (-1,-1), "TOP"),
        ("LEFTPADDING", (0,0), (-1,-1), 7),
        ("RIGHTPADDING", (0,0), (-1,-1), 7),
        ("TOPPADDING", (0,0), (-1,-1), 7),
        ("BOTTOMPADDING", (0,0), (-1,-1), 7),
        ("ROWBACKGROUNDS", (0,1), (-1,-1), [colors.HexColor("#f0f4f7"), colors.white]),
        ("LINEBELOW", (0,0), (-1,0), .5, BLUE),
        ("LINEBELOW", (0,1), (-1,-1), .3, colors.HexColor("#d6dfe6")),
    ]))
    return table, index+1


def blocks(tokens, index=0, stop=None):
    flow = []
    global table_count, heading_count, first_section
    while index < len(tokens):
        tok = tokens[index]
        if tok.type == stop:
            return flow, index+1
        if tok.type == "heading_open":
            inline = tokens[index+1]
            level = int(tok.tag[1:])
            if level == 2 and inline.content.startswith("14 "):
                flow.append(PageBreak())
            if level == 2 and not first_section:
                first_section = True
                flow.append(Spacer(1, 4))
                flow.append(Paragraph("Sommaire", STYLES["h2"]))
                toc = TableOfContents()
                toc.levelStyles = [ParagraphStyle("TOC", parent=BODY, fontSize=9,
                    leading=12.6, spaceBefore=1.3, spaceAfter=1.3,
                    leftIndent=0, firstLineIndent=0)]
                toc.dotsMinLevel = 0
                flow.extend([toc, PageBreak()])
            p = Paragraph(rich(inline), STYLES[{1:"title", 2:"h2", 3:"h3"}[level]])
            if level >= 2:
                heading_count += 1
                p.audit_heading = (level-2, normalized(inline.content), f"section-{heading_count}")
            flow.append(p)
            index += 3
        elif tok.type == "paragraph_open":
            inline = tokens[index+1]
            content = rich(inline)
            if index == 3:
                style = STYLES["meta"]
            else:
                style = STYLES["body"]
            if inline.content.startswith("**Conclusion générale"):
                box = Table([[Paragraph(content, STYLES["callout"])]], colWidths=[WIDTH],
                            spaceAfter=12)
                box.setStyle(TableStyle([
                    ("BACKGROUND",(0,0),(-1,-1),colors.HexColor("#eef4f9")),
                    ("LINEBEFORE",(0,0),(0,-1),2.5,BLUE),
                    ("LEFTPADDING",(0,0),(-1,-1),12), ("RIGHTPADDING",(0,0),(-1,-1),12),
                    ("TOPPADDING",(0,0),(-1,-1),10), ("BOTTOMPADDING",(0,0),(-1,-1),10),
                ]))
                flow.append(box)
            else:
                paragraph = Paragraph(content, style)
                if inline.content.startswith(("**Source :", "**Sources :")):
                    paragraph.keepWithNext = True
                flow.append(paragraph)
            index += 3
        elif tok.type in ("bullet_list_open", "ordered_list_open"):
            ordered = tok.type == "ordered_list_open"
            close = "ordered_list_close" if ordered else "bullet_list_close"
            index += 1
            items = []
            while tokens[index].type != close:
                assert tokens[index].type == "list_item_open"
                content, index = blocks(tokens, index+1, "list_item_close")
                items.append(ListItem(content, leftIndent=12))
            flow.append(ListFlowable(items, bulletType="1" if ordered else "bullet",
                start="1" if ordered else "circle", leftIndent=15,
                bulletFontName="Audit", bulletFontSize=8, bulletOffsetY=1.1,
                spaceAfter=5))
            index += 1
        elif tok.type == "table_open":
            table, index = make_table(tokens, index+1, table_count)
            table_count += 1
            flow.append(table)
        elif tok.type == "fence":
            # Préserver toutes les commandes ; réduire seulement la taille typographique.
            code = normalized(tok.content.rstrip())
            longest = max(pdfmetrics.stringWidth(line,"AuditMono",7.45) for line in code.splitlines())
            assert longest <= WIDTH-16, ("Code trop large", longest, WIDTH)
            flow.append(XPreformatted(html.escape(code), STYLES["code"]))
            index += 1
        else:
            raise ValueError(f"Bloc non pris en charge : {tok.type}")
    return flow, index


if __name__ == "__main__":
    original = SOURCE.read_bytes()
    source = original.decode("utf-8-sig")
    glyphs = pdfmetrics.getFont("Audit").face.charToGlyph
    absent = sorted({c for c in normalized(source) if not c.isspace() and ord(c) not in glyphs})
    if absent:
        raise ValueError(f"Glyphes absents : {absent}")
    tokens = MarkdownIt("commonmark").enable("table").parse(source)
    table_count = heading_count = 0
    first_section = False
    story, _ = blocks(tokens)
    assert table_count == 6
    doc = AuditDoc(str(OUTPUT), pagesize=A4,
        leftMargin=MARGIN_X, rightMargin=MARGIN_X,
        topMargin=MARGIN_TOP, bottomMargin=MARGIN_BOTTOM,
        title="Audit critique du simulateur et des fichiers de fabrication",
        author="Codex", subject="MicroWaveTomography - Rapport détaillé du 18 octobre 2026",
        pageCompression=1, allowSplitting=1)
    frame = Frame(MARGIN_X, MARGIN_BOTTOM, WIDTH, PAGE_H-MARGIN_TOP-MARGIN_BOTTOM,
                  leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0)
    doc.addPageTemplates([PageTemplate(id="Audit", frames=[frame], onPage=footer)])
    doc.multiBuild(story)
    assert SOURCE.read_bytes() == original, "Source modifiée"
    print(json.dumps({"pdf": str(OUTPUT), "bytes": OUTPUT.stat().st_size,
        "source_sha256": hashlib.sha256(original).hexdigest(),
        "tables": table_count, "headings": heading_count}, ensure_ascii=False))
