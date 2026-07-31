import uuid
from pathlib import Path

from app.core.settings import get_settings


class LocalObjectStorage:
    def save_upload(self, data: bytes, filename: str, content_type: str | None = None) -> str:
        ext = Path(filename).suffix.lower() or ".bin"
        key = f"{uuid.uuid4()}{ext}"
        path = get_settings().upload_path / key
        path.write_bytes(data)
        return key

    def resolve_path(self, storage_key: str) -> str:
        return str(get_settings().upload_path / storage_key)
