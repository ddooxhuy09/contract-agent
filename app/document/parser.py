def parse_docx(file_path: str) -> str:
    from docx import Document as DocxDocument
    doc = DocxDocument(file_path)
    text_parts = []
    for p in doc.paragraphs:
        t = p.text.strip()
        if t:
            text_parts.append(t)
    for table in doc.tables:
        for row in table.rows:
            rt = " | ".join(c.text.strip() for c in row.cells if c.text.strip())
            if rt:
                text_parts.append(rt)
    if not text_parts:
        raise ValueError("No text could be extracted from the DOCX file")
    return "\n".join(text_parts)


def parse_pdf(file_path: str) -> str:
    import pdfplumber
    text_parts = []
    try:
        with pdfplumber.open(file_path) as pdf:
            for page in pdf.pages:
                t = page.extract_text()
                if t and t.strip():
                    text_parts.append(t)
    except Exception as e:
        raise ValueError(f"Failed to read PDF file: {e}") from e
    if not text_parts:
        raise ValueError("No text could be extracted from the PDF file")
    return "\n".join(text_parts)


def parse_image(file_path: str) -> str:
    """OCR on this server (Tesseract, Vietnamese): the image itself never goes to the LLM,
    only the text, which is PII-masked like DOCX/PDF text."""
    import pytesseract
    from PIL import Image

    try:
        with Image.open(file_path) as img:
            text = pytesseract.image_to_string(img, lang="vie").strip()
    except (OSError, pytesseract.TesseractError, pytesseract.TesseractNotFoundError) as e:
        raise ValueError(f"Failed to read image file: {e}") from e
    if not text:
        # Never fall back to sending the image to the LLM: that would leak the personal data.
        raise ValueError("No text could be extracted from the image; please upload a PDF or DOCX")
    return text


def parse_document(file_path: str, file_ext: str) -> str:
    ext = file_ext.lower()
    if ext == ".docx":
        return parse_docx(file_path)
    elif ext == ".pdf":
        return parse_pdf(file_path)
    elif ext in (".png", ".jpg", ".jpeg"):
        return parse_image(file_path)
    raise ValueError(f"Unsupported file format: {ext}")
