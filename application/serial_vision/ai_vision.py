from __future__ import annotations

import base64
import json
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from PIL import Image


PROMPT = "Read every visible text item in this equipment-label photo. Return only recognized text, one item per line. Preserve Latin letters, digits, capitalization and punctuation. Do not add explanations or invent values."


class AiVisionRecognizer:
    def recognize(self, provider: str, model: str, token: str, image_path: Path) -> str:
        image = self._image_data(image_path)
        if provider == "openai":
            payload = {"model": model, "store": False, "input": [{"role": "user", "content": [{"type": "input_text", "text": PROMPT}, {"type": "input_image", "image_url": f"data:image/jpeg;base64,{image}", "detail": "high"}]}]}
            response = self._post("https://api.openai.com/v1/responses", payload, {"Authorization": f"Bearer {token}"})
            return self._require_text(self._openai_text(response))
        if provider == "anthropic":
            payload = {"model": model, "max_tokens": 1200, "messages": [{"role": "user", "content": [{"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": image}}, {"type": "text", "text": PROMPT}]}]}
            response = self._post("https://api.anthropic.com/v1/messages", payload, {"x-api-key": token, "anthropic-version": "2023-06-01"})
            return self._require_text("\n".join(str(item.get("text", "")) for item in response.get("content", [])).strip())
        if provider == "gemini":
            payload = {"contents": [{"parts": [{"inline_data": {"mime_type": "image/jpeg", "data": image}}, {"text": PROMPT}]}]}
            response = self._post(f"https://generativelanguage.googleapis.com/v1beta/models/{urllib.parse.quote(model)}:generateContent", payload, {"x-goog-api-key": token})
            return self._require_text("\n".join(str(item.get("text", "")) for item in response.get("candidates", [{}])[0].get("content", {}).get("parts", [])).strip())
        raise RuntimeError("Unsupported AI provider.")

    @staticmethod
    def _image_data(path: Path) -> str:
        with Image.open(path) as source:
            source.thumbnail((1800, 1800))
            from io import BytesIO
            data = BytesIO(); source.convert("RGB").save(data, "JPEG", quality=85)
        return base64.b64encode(data.getvalue()).decode("ascii")

    @staticmethod
    def _require_text(text: str) -> str:
        if not text:
            raise RuntimeError("AI provider returned no recognized text.")
        return text

    @staticmethod
    def _openai_text(response: dict[str, object]) -> str:
        direct = str(response.get("output_text", "")).strip()
        if direct:
            return direct
        fragments: list[str] = []
        for output in response.get("output", []):
            if not isinstance(output, dict):
                continue
            for content in output.get("content", []):
                if isinstance(content, dict) and content.get("type") in {"output_text", "text"}:
                    fragments.append(str(content.get("text", "")))
        return "\n".join(fragment for fragment in fragments if fragment).strip()

    @staticmethod
    def _post(url: str, payload: dict[str, object], headers: dict[str, str]) -> dict[str, object]:
        request = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), method="POST", headers={"Content-Type": "application/json", "Accept": "application/json", **headers})
        try:
            with urllib.request.urlopen(request, timeout=90) as response:
                return json.loads(response.read())
        except urllib.error.HTTPError as error:
            raise RuntimeError(f"HTTP {error.code}: {error.read().decode('utf-8', 'replace')[:500]}") from error
        except urllib.error.URLError as error:
            raise RuntimeError(f"Network error: {error.reason}") from error
