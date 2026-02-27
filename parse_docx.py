import re
from docx import Document

HEADER_RE = re.compile(
    r"^\s*Art\.-Nr\.\s*(\d{4,6})\s*[-–—]\s*(.+?)\s*$",
    re.IGNORECASE
)

def parse_docx(docx_path: str):
    """
    Parses a DOCX that contains repeated sections like:
    'Art.-Nr. 6381 – Farbenfreude'
    followed by 1+ paragraphs of description until the next Art.-Nr header.
    Returns a list of dicts: {art_nr, name, beschreibung_quelle}
    """
    doc = Document(docx_path)

    items = []
    current = None
    desc_lines = []

    def flush():
        nonlocal current, desc_lines
        if not current:
            return
        text = " ".join([ln.strip() for ln in desc_lines if ln.strip()]).strip()
        current["beschreibung_quelle"] = re.sub(r"\s+", " ", text)
        items.append(current)
        current = None
        desc_lines = []

    for p in doc.paragraphs:
        line = (p.text or "").strip()
        if not line:
            continue

        m = HEADER_RE.match(line)
        if m:
            flush()
            current = {
                "art_nr": m.group(1),
                "name": m.group(2).strip(),
                "beschreibung_quelle": "",
            }
        else:
            if current:
                desc_lines.append(line)

    flush()
    return items