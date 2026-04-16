#!/usr/bin/env python3
"""
clean_email.py — Parse and clean newsletter email bodies for TTS.

Two output modes
----------------
1. Structured plain text  (default / always available)
   Headings, paragraphs, and list items are laid out with appropriate blank-line
   spacing so that Kokoro's split_pattern=r'\\n+' produces natural speech pauses.

2. PDF  (--pdf / html_to_pdf())
   A styled PDF is written using reportlab with font sizes tuned to the
   thresholds in pdf_tts.extract_text_from_pdf():
       h1  → 24 pt  (ratio 2.0 → "title")
       h2  → 18 pt  (ratio 1.5 → "section")
       h3  → 14 pt  (ratio 1.17 → "deck")
       body → 12 pt  (ratio 1.0 → "body")
   Pass the resulting PDF to extract_text_from_pdf() for best results.

HTML is always preferred over plain text because it carries explicit structural
information (heading tags, paragraph tags) that can't be recovered from prose.
Plain text is used only when no HTML part is present.

Usage
-----
    python clean_email.py --input email.html --output clean.txt
    python clean_email.py --input email.html --pdf output.pdf
    echo "$BODY" | python clean_email.py            # auto-detects HTML vs text
"""

import re
import sys
import argparse
from html.parser import HTMLParser


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Font sizes for the PDF route — chosen so _classify() in pdf_tts.py assigns
# the right roles when body_size is detected as BODY_PT.
BODY_PT   = 12
H1_PT     = 24   # ratio 2.00 → "title"
H2_PT     = 18   # ratio 1.50 → "section"
H3_PT     = 14   # ratio 1.17 → "deck"
H4_PT     = 13   # ratio 1.08 → "deck"

HEADING_TAGS = {"h1", "h2", "h3", "h4", "h5", "h6"}

SKIP_TAGS = {"script", "style", "head", "noscript", "iframe",
             "svg", "path", "meta", "link", "button", "input", "form",
             "img", "picture", "figure"}


# ---------------------------------------------------------------------------
# HTML structural parser
# Produces a list of (tag, text) tuples representing the document skeleton.
# ---------------------------------------------------------------------------

class _Node:
    __slots__ = ("tag", "text")
    def __init__(self, tag, text):
        self.tag = tag   # "h1","h2","h3","p","li","blockquote","pre" or "body"
        self.text = text


class _StructuralParser(HTMLParser):
    """
    Walk the HTML tree and emit a flat list of _Node objects.
    Heading nesting and inline formatting (bold, italic, links) are preserved
    as plain text — we only care about the block-level structure for TTS.
    """

    BLOCK_CLOSE_TAGS = {"p", "div", "section", "article", "aside",
                        "header", "footer", "nav", "li", "blockquote",
                        "pre", "tr", "td", "th", "figure", "figcaption",
                        "address"} | HEADING_TAGS

    def __init__(self):
        super().__init__()
        self._skip_depth   = 0
        self._current_tag  = "p"     # active block tag
        self._buf          = []       # characters accumulating for current node
        self.nodes         = []       # final output

    # -- helpers --

    def _flush(self):
        text = " ".join("".join(self._buf).split())  # normalise whitespace
        if text:
            self.nodes.append(_Node(self._current_tag, text))
        self._buf = []

    # -- HTMLParser callbacks --

    def handle_starttag(self, tag, attrs):
        tag = tag.lower()
        if tag in SKIP_TAGS:
            self._skip_depth += 1
            return
        if self._skip_depth:
            return
        if tag in self.BLOCK_CLOSE_TAGS:
            self._flush()
            self._current_tag = tag if tag in (HEADING_TAGS | {"li", "blockquote", "pre"}) else "p"
        # <br> injects a space so words don't run together
        if tag == "br":
            self._buf.append(" ")

    def handle_endtag(self, tag):
        tag = tag.lower()
        if tag in SKIP_TAGS:
            self._skip_depth = max(0, self._skip_depth - 1)
            return
        if self._skip_depth:
            return
        if tag in self.BLOCK_CLOSE_TAGS:
            self._flush()
            self._current_tag = "p"

    def handle_data(self, data):
        if not self._skip_depth:
            self._buf.append(data)

    def handle_entityref(self, name):
        if self._skip_depth:
            return
        mapping = {
            "amp": "&", "lt": "<", "gt": ">", "quot": '"', "apos": "'",
            "nbsp": " ", "mdash": "—", "ndash": "–",
            "ldquo": "\u201c", "rdquo": "\u201d",
            "lsquo": "\u2018", "rsquo": "\u2019",
            "hellip": "…", "bull": "•",
        }
        self._buf.append(mapping.get(name, ""))

    def handle_charref(self, name):
        if self._skip_depth:
            return
        try:
            ch = chr(int(name[1:], 16) if name.lower().startswith("x") else int(name))
            self._buf.append(ch)
        except (ValueError, OverflowError):
            pass

    def close(self):
        super().close()
        self._flush()   # flush any dangling buffer


def _parse_html(html: str) -> list:
    """Return a list of _Node objects representing the email's block structure."""
    p = _StructuralParser()
    p.feed(html)
    p.close()
    return p.nodes


# ---------------------------------------------------------------------------
# Boilerplate detection  (applied to nodes, not raw lines)
# ---------------------------------------------------------------------------

HEADER_BOILERPLATE = [
    r'^view\s+(this\s+)?(email|message|newsletter|issue)\s+(in|online|in\s+your)',
    r'^read\s+online',
    r'^view\s+online',
    r'^open\s+in\s+browser',
    r'^having\s+trouble\s+(reading|viewing)',
    r'^if\s+you.{0,20}(can.t|cannot)\s+(see|view|read)',
]

FOOTER_BOILERPLATE = [
    r'unsubscribe',
    r'manage\s+(your\s+)?(preferences|subscription)',
    r'opt.out',
    r'receiving\s+this',               # "you're receiving this", "you are receiving this", etc.
    r'you\s+received\s+this',          # "you received this because…", "you received this email…"
    r'this\s+email\s+was\s+sent\s+to',
    r'©\s*\d{4}',
    r'copyright\s+©?\s*\d{4}',
    r'all\s+rights\s+reserved',
    r'our\s+(mailing|postal)\s+address',
    r'privacy\s+policy',
    r'terms\s+(of\s+)?(service|use)',
    r'powered\s+by\s+(substack|mailchimp|beehiiv|convertkit|klaviyo|sendgrid)',
    r'sent\s+via\s+(substack|mailchimp|beehiiv)',
    r'forwarded\s+this\s+(email|newsletter)',
    r'not\s+want\s+to\s+receive',
    r'no\s+longer\s+wish\s+to\s+receive',
    r'update\s+your\s+(email\s+)?preferences',
    r'view\s+(this\s+)?(email|message|newsletter)\s+(in|online)',  # also catches footer "view online" links
    r'view\s+online',
    r'read\s+this\s+online',
]

JUNK_TEXT = [
    r'^\s*\|\s*$',
    r'^\s*[-=]{3,}\s*$',
    r'^\s*\d+\s*$',
]


def _is_boilerplate(text: str, patterns: list) -> bool:
    low = text.lower()
    return any(re.search(p, low) for p in patterns)


def _clean_nodes(nodes: list) -> list:
    """Strip header/footer boilerplate nodes and obvious junk."""
    n = len(nodes)

    # --- header: scan first 5 nodes ---
    start = 0
    for i in range(min(5, n)):
        if _is_boilerplate(nodes[i].text, HEADER_BOILERPLATE):
            start = i + 1

    # --- footer: scan second half ---
    half = n // 2
    end = n
    for i in range(half, n):
        if _is_boilerplate(nodes[i].text, FOOTER_BOILERPLATE):
            end = i
            break

    result = nodes[start:end]

    # --- remove junk lines ---
    result = [nd for nd in result
              if not _is_boilerplate(nd.text, JUNK_TEXT)
              and len(nd.text.strip()) > 1]

    return result


# ---------------------------------------------------------------------------
# Output Route A: structured plain text
# ---------------------------------------------------------------------------

def nodes_to_text(nodes: list) -> str:
    """
    Convert cleaned nodes into plain text with Kokoro-friendly spacing.

    Headings get a blank line before and after so they form their own speech
    segment when Kokoro splits on \\n+.  Lists are rendered as sentences with
    a period appended if none is present.
    """
    parts = []
    prev_was_heading = False

    for nd in nodes:
        text = nd.text.strip()
        if not text:
            continue

        if nd.tag in HEADING_TAGS:
            # Always surround headings with blank lines
            parts.append("")
            parts.append(text)
            parts.append("")
            prev_was_heading = True

        elif nd.tag == "li":
            # List items: convert to a declarative sentence form
            if text and text[-1] not in ".!?:":
                text = text + "."
            parts.append(text)
            prev_was_heading = False

        elif nd.tag == "blockquote":
            parts.append("")
            parts.append(text)
            parts.append("")
            prev_was_heading = False

        else:
            # Body paragraph
            if prev_was_heading:
                # Already have blank lines from the heading — don't double-up
                parts.append(text)
            else:
                parts.append(text)
            prev_was_heading = False

    raw = "\n".join(parts)
    # Collapse runs of 3+ blank lines to 2
    raw = re.sub(r'\n{3,}', '\n\n', raw)
    return raw.strip()


# ---------------------------------------------------------------------------
# Output Route B: HTML → styled PDF via reportlab
# ---------------------------------------------------------------------------

def html_to_pdf(html: str, pdf_path: str, subject: str = "") -> None:
    """
    Render the email as a styled PDF using reportlab.

    Font sizes are calibrated to the thresholds in pdf_tts._classify() so
    that extract_text_from_pdf() assigns the correct roles:
        h1  → 24 pt  (title)
        h2  → 18 pt  (section)
        h3/h4 → 14 pt (deck)
        body → 12 pt  (body)

    Pass the resulting PDF path to pdf_tts.extract_text_from_pdf() for
    paragraph reconstruction and then to text_to_audio().
    """
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.enums import TA_LEFT
    # In reportlab, 1 unit = 1 point — no conversion needed

    def _esc(s):
        """Escape special reportlab markup characters."""
        return (s.replace("&", "&amp;")
                 .replace("<", "&lt;")
                 .replace(">", "&gt;"))

    # Style definitions — keep leading generous so PyMuPDF doesn't merge lines
    styles = {
        "h1": ParagraphStyle("h1", fontSize=H1_PT, leading=H1_PT * 1.3,
                             spaceBefore=18, spaceAfter=8,
                             alignment=TA_LEFT),
        "h2": ParagraphStyle("h2", fontSize=H2_PT, leading=H2_PT * 1.3,
                             spaceBefore=14, spaceAfter=6,
                             alignment=TA_LEFT),
        "h3": ParagraphStyle("h3", fontSize=H3_PT, leading=H3_PT * 1.3,
                             spaceBefore=10, spaceAfter=4,
                             alignment=TA_LEFT),
        "h4": ParagraphStyle("h4", fontSize=H4_PT, leading=H4_PT * 1.3,
                             spaceBefore=8, spaceAfter=4,
                             alignment=TA_LEFT),
        "p":  ParagraphStyle("body", fontSize=BODY_PT, leading=BODY_PT * 1.6,
                             spaceBefore=0, spaceAfter=6,
                             alignment=TA_LEFT),
        "li": ParagraphStyle("li", fontSize=BODY_PT, leading=BODY_PT * 1.6,
                             spaceBefore=0, spaceAfter=3,
                             leftIndent=20, alignment=TA_LEFT),
        "blockquote": ParagraphStyle("bq", fontSize=BODY_PT, leading=BODY_PT * 1.6,
                                     spaceBefore=6, spaceAfter=6,
                                     leftIndent=30, alignment=TA_LEFT),
    }
    default_style = styles["p"]

    nodes = _parse_html(html)
    nodes = _clean_nodes(nodes)

    doc = SimpleDocTemplate(pdf_path, pagesize=letter,
                            leftMargin=72, rightMargin=72,
                            topMargin=72, bottomMargin=72)
    story = []

    # Optional subject line as H1 if the email itself doesn't start with one
    if subject and (not nodes or nodes[0].tag not in {"h1"}):
        story.append(Paragraph(_esc(subject), styles["h1"]))
        story.append(Spacer(1, 6 * pt))

    for nd in nodes:
        text = _esc(nd.text.strip())
        if not text:
            continue
        tag = nd.tag if nd.tag in styles else "p"
        # List items: append period if missing (reads better as spoken prose)
        if tag == "li" and nd.text[-1] not in ".!?":
            text += "."
        story.append(Paragraph(text, styles[tag]))

    if not story:
        story.append(Paragraph("(no content)", default_style))

    doc.build(story)


# ---------------------------------------------------------------------------
# Unified public API
# ---------------------------------------------------------------------------

def clean_body(plain: str = "", html: str = "") -> str:
    """
    Return cleaned, TTS-ready plain text from an email's body parts.

    HTML is preferred because it carries structural information (headings,
    paragraphs) that improves Kokoro output.  Plain text is used only when
    no usable HTML is present.
    """
    # --- Try HTML first ---
    if html and html.strip() and len(html.strip()) >= 100:
        nodes = _parse_html(html)
        nodes = _clean_nodes(nodes)
        text = nodes_to_text(nodes)
        if len(text) >= 80:
            return text

    # --- Fallback: plain text ---
    if not plain or not plain.strip():
        return ""

    raw = plain.strip()
    lines = raw.splitlines()

    # Apply the same boilerplate stripping to plain-text lines
    n = len(lines)
    start = 0
    for i in range(min(5, n)):
        if _is_boilerplate(lines[i], HEADER_BOILERPLATE):
            start = i + 1
    half = n // 2
    end = n
    for i in range(half, n):
        if _is_boilerplate(lines[i], FOOTER_BOILERPLATE):
            end = i
            break
    lines = lines[start:end]
    lines = [l for l in lines if not _is_boilerplate(l, JUNK_TEXT)]

    # Collapse blanks
    out, prev_blank = [], False
    for l in lines:
        blank = not l.strip()
        if blank and prev_blank:
            continue
        out.append(l)
        prev_blank = blank

    result = "\n".join(out).strip()
    result = re.sub(r'[ \t]{2,}', ' ', result)
    return result


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser(
        description="Clean a newsletter email body for TTS."
    )
    ap.add_argument("--input",   "-i", help="Input file (default: stdin)")
    ap.add_argument("--output",  "-o", help="Output file (default: stdout)")
    ap.add_argument("--pdf",     "-p", metavar="PDF_PATH",
                    help="Write a styled PDF instead of plain text (requires reportlab)")
    ap.add_argument("--subject", "-s", default="",
                    help="Email subject — prepended as H1 in PDF mode")
    ap.add_argument("--html",    action="store_true",
                    help="Treat input as HTML (default: auto-detect)")
    args = ap.parse_args()

    raw = open(args.input).read() if args.input else sys.stdin.read()
    is_html = args.html or bool(re.search(r'<html|<body|<div|<p\b', raw, re.IGNORECASE))

    if args.pdf:
        if not is_html:
            # Wrap plain text in minimal HTML so the parser can handle it
            raw = "<html><body>" + "".join(f"<p>{l}</p>" for l in raw.splitlines() if l.strip()) + "</body></html>"
        html_to_pdf(raw, args.pdf, subject=args.subject)
        print(f"PDF written to: {args.pdf}", file=sys.stderr)
        return

    if is_html:
        result = clean_body(html=raw)
    else:
        result = clean_body(plain=raw)

    if args.output:
        with open(args.output, "w") as f:
            f.write(result)
    else:
        print(result)


if __name__ == "__main__":
    main()
