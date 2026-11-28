import pytest
from app.document.parser import parse_pdf, parse_document


def test_parse_pdf_invalid_path():
    with pytest.raises(ValueError):
        parse_pdf("nonexistent.pdf")


def test_parse_pdf_empty_file(tmp_path):
    p = tmp_path / "empty.pdf"
    p.write_text("not a pdf")
    with pytest.raises(ValueError):
        parse_pdf(str(p))


def test_parse_image_ocr_is_local_and_never_calls_llm(tmp_path, monkeypatch):
    import pytesseract
    from PIL import Image
    import app.agents.llm_client as llm_client

    img = tmp_path / "hd.png"
    Image.new("RGB", (10, 10), "white").save(img)
    monkeypatch.setattr(llm_client, "get_chat_model", lambda *a, **k: pytest.fail("image sent to LLM"))
    monkeypatch.setattr(pytesseract, "image_to_string", lambda im, lang: " Họ tên: Nguyễn Văn A \n")
    assert parse_document(str(img), ".png") == "Họ tên: Nguyễn Văn A"

    monkeypatch.setattr(pytesseract, "image_to_string", lambda im, lang: "  ")
    with pytest.raises(ValueError, match="PDF or DOCX"):
        parse_document(str(img), ".png")


def test_parse_document_unsupported():
    with pytest.raises(ValueError, match="Unsupported"):
        parse_document("test.xyz", ".xyz")


@pytest.mark.parametrize("size, expected", [
    ((100, 150), (400, 600)),  # Cap enlargement at 4x.
    ((1000, 1500), (2000, 3000)),
    ((2500, 100), (2500, 100)),  # Preserve large images without downscaling.
])
def test_image_preprocessing_preserves_aspect_ratio_and_large_images(tmp_path, monkeypatch, size, expected):
    import pytesseract
    from PIL import Image

    path = tmp_path / "ocr.png"
    Image.new("RGBA", size, "white").save(path)
    seen = []

    def ocr(image, lang):
        seen.append((image.mode, image.size, lang))
        return "Điều 1. Hợp đồng lao động"

    monkeypatch.setattr(pytesseract, "image_to_string", ocr)
    assert parse_document(str(path), ".png") == "Điều 1. Hợp đồng lao động"
    assert seen == [("L", expected, "vie")]
