"""Convert a vbpl.vn document's raw article HTML + attributes + relation
references into the 3 on-disk artifacts: van_ban.md, thuoc_tinh.json, luoc_do.json.
"""
import json
import re

from bs4 import BeautifulSoup, NavigableString, Tag

# referenceType -> relation-category name, confirmed against Thong tu 100/2026/TT-BTC
# (type 3 = 5 "Can cu ban hanh" items, type 1 = 6 "Van ban bi bai bo" items). Other
# type codes are unconfirmed until a document exercising them gets crawled.
REFERENCE_TYPE_NAMES = {
    1: "van_ban_bi_bai_bo",
    3: "can_cu_ban_hanh",
}

_BOLD_STYLE_RE = re.compile(r"font-weight\s*:\s*bold")
_ITALIC_STYLE_RE = re.compile(r"font-style\s*:\s*italic")
_WS_RE = re.compile(r"[ \t]+")
_NBSP = "\xa0"


def _is_bold(tag: Tag) -> bool:
    if tag.name in ("b", "strong"):
        return True
    return bool(_BOLD_STYLE_RE.search(tag.get("style", "")))


def _is_italic(tag: Tag) -> bool:
    if tag.name in ("i", "em"):
        return True
    return bool(_ITALIC_STYLE_RE.search(tag.get("style", "")))


def _inline_to_markdown(node, ambient_bold: bool = False, ambient_italic: bool = False) -> str:
    """Recursively render an element's inline content to Markdown, converting
    bold/italic (real <b>/<i> tags AND inline font-weight/font-style CSS, which
    is how vbpl.vn actually marks them up) and <br> into line breaks.

    vbpl.vn's HTML nests redundant bold tags (e.g. <strong><b>text</b></strong>),
    so bold/italic state is threaded down as "ambient": markers are only emitted
    where bold/italic newly turns on relative to the parent, not on every nested
    tag that repeats it (which would otherwise produce "****text****").
    """
    if isinstance(node, NavigableString):
        return str(node).replace(_NBSP, " ")

    if node.name == "br":
        return "\n"

    if node.name in ("script", "style"):
        return ""

    this_bold = _is_bold(node)
    this_italic = _is_italic(node)
    child_bold = ambient_bold or this_bold
    child_italic = ambient_italic or this_italic

    inner = "".join(_inline_to_markdown(child, child_bold, child_italic) for child in node.children)

    apply_bold = this_bold and not ambient_bold
    apply_italic = this_italic and not ambient_italic
    if not (apply_bold or apply_italic):
        return inner

    # Apply markers per line so a bold span containing a <br> doesn't produce
    # "**line one\nline two**" (which most Markdown renderers won't parse as bold).
    def wrap_line(line: str) -> str:
        stripped = line.strip()
        if not stripped:
            return ""
        if apply_bold and apply_italic:
            return f"***{stripped}***"
        if apply_bold:
            return f"**{stripped}**"
        if apply_italic:
            return f"*{stripped}*"
        return stripped

    return "\n".join(wrap_line(l) for l in inner.split("\n"))


def _block_text(el: Tag) -> str:
    """Render a block-level element (p, td, ...) to a single clean Markdown string."""
    raw = _inline_to_markdown(el)
    lines = [_WS_RE.sub(" ", l).strip() for l in raw.split("\n")]
    return "\n".join(l for l in lines if l)


def _table_to_markdown(table: Tag) -> str:
    row_blocks = []
    for tr in table.find_all("tr", recursive=True):
        cells = tr.find_all(["td", "th"], recursive=False)
        cell_texts = [_block_text(c) for c in cells]
        cell_texts = [c for c in cell_texts if c]
        if cell_texts:
            row_blocks.append("  \n".join(cell_texts) if len(cell_texts) == 1 else " | ".join(cell_texts))
    return "\n\n".join(row_blocks)


def html_to_markdown(html: str) -> str:
    """Convert the article HTML into Markdown, promoting prov-article/prov-clause
    elements to headings/list items and embedding their vbpl element id as an
    HTML comment so citations can be traced back to the source element.

    Walks only the DIRECT children of <body> (p/table are siblings there, not
    nested in each other) so a table's <p> cells aren't re-emitted a second
    time when the top-level scan also visits <p> tags.
    """
    soup = BeautifulSoup(html, "html.parser")
    body = soup.body or soup

    lines: list[str] = []
    current_article_clauses: list[str] = []

    def flush_clauses():
        if current_article_clauses:
            lines.extend(current_article_clauses)
            lines.append("")
            current_article_clauses.clear()

    for el in body.find_all(["p", "table"], recursive=False):
        if el.name == "table":
            flush_clauses()
            table_md = _table_to_markdown(el)
            if table_md:
                lines.append(table_md)
                lines.append("")
            continue

        classes = el.get("class") or []
        text = _block_text(el)
        if not text:
            continue

        if "prov-article" in classes:
            flush_clauses()
            el_id = el.get("id", "")
            lines.append(f"## {text}")
            if el_id:
                lines.append(f"<!-- article_id: {el_id} -->")
            lines.append("")
        elif "prov-clause" in classes:
            el_id = el.get("id", "")
            marker = f" <!-- clause_id: {el_id} -->" if el_id else ""
            current_article_clauses.append(f"{text}{marker}")
        elif "prov-content" in classes:
            flush_clauses()
            lines.append(text)
            lines.append("")
        else:
            flush_clauses()
            lines.append(text)
            lines.append("")

    flush_clauses()
    return "\n".join(lines).strip() + "\n"


def build_thuoc_tinh(attributes: dict) -> dict:
    doc_type = attributes.get("docType") or {}
    eff_status = attributes.get("effStatus") or {}
    agency = attributes.get("agencyName")
    majors = [m.get("name") for m in (attributes.get("documentMajors") or [])]
    fields = [f.get("name") for f in (attributes.get("documentFields") or [])]
    issues = attributes.get("documentIssues") or []

    return {
        "doc_id": attributes.get("id"),
        "doc_num": attributes.get("docNum"),
        "doc_type": doc_type.get("name"),
        "title": attributes.get("title"),
        "majors": majors,
        "fields": fields,
        "issue_date": attributes.get("issueDate"),
        "eff_from": attributes.get("effFrom"),
        "eff_to": attributes.get("effTo"),
        "eff_status": eff_status.get("name"),
        "eff_status_code": eff_status.get("code"),
        "agency": agency,
        "signers": [
            {"name": i.get("personName"), "title": i.get("jobTitleName")}
            for i in issues
        ],
    }


def build_luoc_do(attributes: dict) -> dict:
    references = attributes.get("references") or []
    grouped: dict[str, list[dict]] = {}
    for ref in references:
        type_code = ref.get("referenceType")
        category = REFERENCE_TYPE_NAMES.get(type_code, f"reference_type_{type_code}")
        target = ref.get("targetDocument") or {}
        grouped.setdefault(category, []).append(
            {
                "doc_id": target.get("id"),
                "doc_num": target.get("docNum"),
                "title": target.get("title"),
                "issue_date": target.get("issueDate"),
                "eff_from": target.get("effFrom"),
                "eff_to": target.get("effTo"),
                "status": target.get("status"),
            }
        )
    return {"doc_id": attributes.get("id"), "relations": grouped}


def safe_folder_name(title: str, max_len: int = 150) -> str:
    """Sanitize a document title into a filesystem-safe folder name, keeping
    it human-readable (unlike slugify_title, which is for URL slugs)."""
    cleaned = re.sub(r"[/\\]", "-", title)
    cleaned = re.sub(r'[<>:"|?*]', "", cleaned).strip()
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned[:max_len].rstrip(" .")
