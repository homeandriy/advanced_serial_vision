from __future__ import annotations

from datetime import datetime
from io import BytesIO
import re
from zoneinfo import ZoneInfo

import qrcode
from barcode import Code128
from barcode.writer import ImageWriter


def normalized_code_type(code_type: str) -> str:
    if code_type in {"qr", "qrcode"}:
        return "qrcode"
    if code_type == "barcode":
        return "barcode"
    raise ValueError("code_type_invalid")


def generated_code_filename(value: str, code_type: str, generated_at: datetime | None = None) -> str:
    normalized_type = normalized_code_type(code_type)
    safe_value = re.sub(r"[^A-Za-z0-9]", "", value.strip()) or "code"
    timestamp = (generated_at or datetime.now(ZoneInfo("Europe/Kyiv"))).strftime("%H_%M_%d_%m_%Y")
    return f"{normalized_type}_{safe_value}_{timestamp}.png"


def generate_code_png(value: str, code_type: str) -> bytes:
    content = value.strip()
    if not content:
        raise ValueError("code_value_empty")
    stream = BytesIO()
    if normalized_code_type(code_type) == "qrcode":
        image = qrcode.make(content)
        image.save(stream, format="PNG")
    else:
        Code128(content, writer=ImageWriter()).write(stream, options={"write_text": False})
    return stream.getvalue()
