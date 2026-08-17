"""Ensure full hierarchy FK chain with 'Không có' scaffolds; RAG paths stay sparse.

Scaffold ltree labels (not real VB structure): ._P ._C ._M ._TM under parent path.
Works before/after migration (with or without child doc_id columns).
"""

from __future__ import annotations

import re

KHONG_CO = "Không có"

SCAFFOLD_PART = "_P"
SCAFFOLD_CHAPTER = "_C"
SCAFFOLD_SECTION = "_M"
SCAFFOLD_SUB_SECTION = "_TM"

_HAS_DOC_ID: dict[str, bool] = {}


def scaffold_child_path(parent_path: str, token: str) -> str:
    return f"{parent_path}.{token}" if parent_path else token


def _has_doc_id_col(cur, table: str) -> bool:
    if table not in _HAS_DOC_ID:
        cur.execute(
            """
            SELECT 1 FROM information_schema.columns
            WHERE table_schema = 'public' AND table_name = %s AND column_name = 'doc_id'
            """,
            (table,),
        )
        _HAS_DOC_ID[table] = cur.fetchone() is not None
    return _HAS_DOC_ID[table]


def ensure_doc_root_path(cur, doc_id: str, preferred_path: str | None = None) -> str:
    from app.infrastructure.legal_corpus.muc_luc_paths import sanitize_doc_id_for_ltree

    cur.execute("SELECT path::text FROM legal_documents WHERE doc_id = %s", (doc_id,))
    row = cur.fetchone()
    if not row:
        raise ValueError(f"legal_documents missing doc_id={doc_id}")
    if row[0]:
        return row[0]
    root = preferred_path.split(".", 1)[0] if preferred_path else sanitize_doc_id_for_ltree(doc_id)
    cur.execute(
        "UPDATE legal_documents SET path = %s::ltree WHERE doc_id = %s AND path IS NULL",
        (root, doc_id),
    )
    return root


def _get_id_by_path(cur, table: str, path: str) -> int | None:
    cur.execute(f"SELECT id FROM {table} WHERE path = %s::ltree", (path,))
    row = cur.fetchone()
    return int(row[0]) if row else None


def ensure_part(cur, doc_id: str, doc_root: str, real_part_path: str | None = None) -> int:
    if real_part_path:
        pid = _get_id_by_path(cur, "legal_parts", real_part_path)
        if pid:
            return pid
    cur.execute(
        """
        SELECT id FROM legal_parts WHERE doc_id = %s
        ORDER BY CASE WHEN title = %s THEN 1 ELSE 0 END, id
        LIMIT 1
        """,
        (doc_id, KHONG_CO),
    )
    row = cur.fetchone()
    if row:
        return int(row[0])
    # prefer real part if any (title != Không có)
    cur.execute(
        """
        SELECT id FROM legal_parts WHERE doc_id = %s AND title IS DISTINCT FROM %s
        ORDER BY id LIMIT 1
        """,
        (doc_id, KHONG_CO),
    )
    row = cur.fetchone()
    if row:
        return int(row[0])

    path = scaffold_child_path(doc_root, SCAFFOLD_PART)
    existing = _get_id_by_path(cur, "legal_parts", path)
    if existing:
        return existing
    cur.execute(
        """
        INSERT INTO legal_parts (doc_id, title, content, path, parent_path)
        VALUES (%s, %s, %s, %s::ltree, %s::ltree)
        RETURNING id
        """,
        (doc_id, KHONG_CO, KHONG_CO, path, doc_root),
    )
    return int(cur.fetchone()[0])


def ensure_chapter(
    cur, part_id: int, part_path: str, real_chapter_path: str | None, doc_id: str
) -> int:
    if real_chapter_path:
        cid = _get_id_by_path(cur, "legal_chapters", real_chapter_path)
        if cid:
            cur.execute(
                "UPDATE legal_chapters SET part_id = COALESCE(part_id, %s) WHERE id = %s",
                (part_id, cid),
            )
            return cid
    path = scaffold_child_path(part_path, SCAFFOLD_CHAPTER)
    existing = _get_id_by_path(cur, "legal_chapters", path)
    if existing:
        cur.execute(
            "UPDATE legal_chapters SET part_id = COALESCE(part_id, %s) WHERE id = %s",
            (part_id, existing),
        )
        return existing
    if _has_doc_id_col(cur, "legal_chapters"):
        cur.execute(
            """
            INSERT INTO legal_chapters (doc_id, part_id, title, content, path, parent_path)
            VALUES (%s, %s, %s, %s, %s::ltree, %s::ltree)
            RETURNING id
            """,
            (doc_id, part_id, KHONG_CO, KHONG_CO, path, part_path),
        )
    else:
        cur.execute(
            """
            INSERT INTO legal_chapters (part_id, title, content, path, parent_path)
            VALUES (%s, %s, %s, %s::ltree, %s::ltree)
            RETURNING id
            """,
            (part_id, KHONG_CO, KHONG_CO, path, part_path),
        )
    return int(cur.fetchone()[0])


def ensure_section(
    cur, chapter_id: int, chapter_path: str, real_section_path: str | None, doc_id: str
) -> int:
    if real_section_path:
        sid = _get_id_by_path(cur, "legal_sections", real_section_path)
        if sid:
            cur.execute(
                "UPDATE legal_sections SET chapter_id = COALESCE(chapter_id, %s) WHERE id = %s",
                (chapter_id, sid),
            )
            return sid
    path = scaffold_child_path(chapter_path, SCAFFOLD_SECTION)
    existing = _get_id_by_path(cur, "legal_sections", path)
    if existing:
        cur.execute(
            "UPDATE legal_sections SET chapter_id = COALESCE(chapter_id, %s) WHERE id = %s",
            (chapter_id, existing),
        )
        return existing
    if _has_doc_id_col(cur, "legal_sections"):
        cur.execute(
            """
            INSERT INTO legal_sections (doc_id, chapter_id, title, content, path, parent_path)
            VALUES (%s, %s, %s, %s, %s::ltree, %s::ltree)
            RETURNING id
            """,
            (doc_id, chapter_id, KHONG_CO, KHONG_CO, path, chapter_path),
        )
    else:
        cur.execute(
            """
            INSERT INTO legal_sections (chapter_id, title, content, path, parent_path)
            VALUES (%s, %s, %s, %s::ltree, %s::ltree)
            RETURNING id
            """,
            (chapter_id, KHONG_CO, KHONG_CO, path, chapter_path),
        )
    return int(cur.fetchone()[0])


def ensure_sub_section(
    cur,
    section_id: int,
    section_path: str,
    real_sub_section_path: str | None,
    doc_id: str,
) -> int:
    if real_sub_section_path:
        ssid = _get_id_by_path(cur, "legal_sub_sections", real_sub_section_path)
        if ssid:
            cur.execute(
                "UPDATE legal_sub_sections SET section_id = COALESCE(section_id, %s) WHERE id = %s",
                (section_id, ssid),
            )
            return ssid
    path = scaffold_child_path(section_path, SCAFFOLD_SUB_SECTION)
    existing = _get_id_by_path(cur, "legal_sub_sections", path)
    if existing:
        cur.execute(
            "UPDATE legal_sub_sections SET section_id = COALESCE(section_id, %s) WHERE id = %s",
            (section_id, existing),
        )
        return existing
    if _has_doc_id_col(cur, "legal_sub_sections"):
        cur.execute(
            """
            INSERT INTO legal_sub_sections (doc_id, section_id, title, content, path, parent_path)
            VALUES (%s, %s, %s, %s, %s::ltree, %s::ltree)
            RETURNING id
            """,
            (doc_id, section_id, KHONG_CO, KHONG_CO, path, section_path),
        )
    else:
        cur.execute(
            """
            INSERT INTO legal_sub_sections (section_id, title, content, path, parent_path)
            VALUES (%s, %s, %s, %s::ltree, %s::ltree)
            RETURNING id
            """,
            (section_id, KHONG_CO, KHONG_CO, path, section_path),
        )
    return int(cur.fetchone()[0])


def resolve_ancestors_from_article_path(article_path: str) -> dict[str, str | None]:
    parts = article_path.split(".")
    chapter = section = sub_section = part = None
    for i in range(1, len(parts)):
        prefix = ".".join(parts[: i + 1])
        lab = parts[i]
        if re.fullmatch(r"P\d+", lab):
            part = prefix
        elif re.fullmatch(r"C\d+", lab):
            chapter = prefix
        elif re.fullmatch(r"M\d+", lab):
            section = prefix
        elif re.fullmatch(r"TM\d+", lab):
            sub_section = prefix
        elif re.fullmatch(r"D\d+", lab):
            break
    return {
        "part": part,
        "chapter": chapter,
        "section": section,
        "sub_section": sub_section,
    }


def ensure_chain_for_article(cur, doc_id: str, article_path: str) -> int:
    doc_root = ensure_doc_root_path(cur, doc_id, article_path)
    anc = resolve_ancestors_from_article_path(article_path)

    part_id = ensure_part(cur, doc_id, doc_root, anc["part"])
    cur.execute("SELECT path::text FROM legal_parts WHERE id = %s", (part_id,))
    part_path = cur.fetchone()[0]

    chapter_id = ensure_chapter(cur, part_id, part_path, anc["chapter"], doc_id)
    cur.execute("SELECT path::text FROM legal_chapters WHERE id = %s", (chapter_id,))
    chapter_path = cur.fetchone()[0]

    section_id = ensure_section(cur, chapter_id, chapter_path, anc["section"], doc_id)
    cur.execute("SELECT path::text FROM legal_sections WHERE id = %s", (section_id,))
    section_path = cur.fetchone()[0]

    return ensure_sub_section(cur, section_id, section_path, anc["sub_section"], doc_id)


def fill_null_attributes(cur) -> None:
    for table, cols in (
        ("legal_parts", ("title", "content")),
        ("legal_chapters", ("title", "content")),
        ("legal_sections", ("title", "content")),
        ("legal_sub_sections", ("title", "content")),
        ("legal_articles", ("title", "content")),
        ("legal_clauses", ("title", "content")),
        ("legal_points", ("title", "content")),
    ):
        for col in cols:
            cur.execute(
                f"UPDATE {table} SET {col} = %s WHERE {col} IS NULL OR BTRIM({col}) = ''",
                (KHONG_CO,),
            )
