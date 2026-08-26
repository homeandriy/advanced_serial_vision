from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from xml.etree import ElementTree
from zipfile import BadZipFile, ZipFile


SPREADSHEET_NAMESPACE = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
RELATIONSHIPS_NAMESPACE = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"


@dataclass(frozen=True)
class ImportedModel:
    name: str
    device_type: str
    service: str


@dataclass(frozen=True)
class ModelImportData:
    models: list[ImportedModel]
    errors: list[str]


def read_models_xlsx(path: Path) -> ModelImportData:
    if path.suffix.lower() != ".xlsx":
        raise ValueError("model_import_file_type")
    try:
        with ZipFile(path) as archive:
            shared = _shared_strings(archive)
            sheet_path = _models_sheet_path(archive)
            rows = _rows(archive.read(sheet_path), shared)
    except (BadZipFile, KeyError, OSError, ElementTree.ParseError) as error:
        raise ValueError("model_import_file_invalid") from error
    return _parse_rows(rows)


def _shared_strings(archive: ZipFile) -> list[str]:
    if "xl/sharedStrings.xml" not in archive.namelist():
        return []
    root = ElementTree.fromstring(archive.read("xl/sharedStrings.xml"))
    return ["".join(node.itertext()) for node in root.findall(f"{SPREADSHEET_NAMESPACE}si")]


def _models_sheet_path(archive: ZipFile) -> str:
    workbook = ElementTree.fromstring(archive.read("xl/workbook.xml"))
    relationships = ElementTree.fromstring(archive.read("xl/_rels/workbook.xml.rels"))
    targets = {relation.attrib["Id"]: relation.attrib["Target"] for relation in relationships}
    sheets = workbook.findall(f"{SPREADSHEET_NAMESPACE}sheets/{SPREADSHEET_NAMESPACE}sheet")
    sheet = next((item for item in sheets if item.attrib.get("name", "").casefold() in {"models", "моделі"}), sheets[0] if sheets else None)
    if sheet is None:
        raise KeyError("worksheet")
    target = targets[sheet.attrib[f"{RELATIONSHIPS_NAMESPACE}id"]].lstrip("/")
    return target if target.startswith("xl/") else f"xl/{target}"


def _rows(xml: bytes, shared: list[str]) -> list[list[str]]:
    root = ElementTree.fromstring(xml)
    result: list[list[str]] = []
    for row in root.findall(f".//{SPREADSHEET_NAMESPACE}row"):
        values: dict[int, str] = {}
        for cell in row.findall(f"{SPREADSHEET_NAMESPACE}c"):
            reference = cell.attrib.get("r", "A1")
            column = _column_index(reference)
            value = cell.find(f"{SPREADSHEET_NAMESPACE}v")
            inline = cell.find(f"{SPREADSHEET_NAMESPACE}is")
            if cell.attrib.get("t") == "s" and value is not None:
                values[column] = shared[int(value.text or "0")]
            elif inline is not None:
                values[column] = "".join(inline.itertext())
            else:
                values[column] = "" if value is None else value.text or ""
        result.append([values.get(index, "") for index in range(max(values, default=-1) + 1)])
    return result


def _column_index(reference: str) -> int:
    letters = "".join(character for character in reference if character.isalpha())
    result = 0
    for character in letters:
        result = result * 26 + ord(character.upper()) - ord("A") + 1
    return result - 1


def _parse_rows(rows: list[list[str]]) -> ModelImportData:
    if not rows:
        raise ValueError("model_import_headers")
    headers = {_normalize_header(value): index for index, value in enumerate(rows[0])}
    name_column = _find_header(headers, "name", "model", "назва", "назвамоделі")
    type_column = _find_header(headers, "devicetype", "type", "тип")
    service_column = _find_header(headers, "service", "послуга")
    if None in {name_column, type_column, service_column}:
        raise ValueError("model_import_headers")
    models: list[ImportedModel] = []
    errors: list[str] = []
    for row_number, row in enumerate(rows[1:], start=2):
        name = _value(row, name_column).strip()
        device_type = _normalize_type(_value(row, type_column))
        service = _normalize_service(_value(row, service_column))
        if not any(row):
            continue
        if not name or device_type is None or service is None:
            errors.append(str(row_number))
            continue
        models.append(ImportedModel(name, device_type, service))
    return ModelImportData(models, errors)


def _normalize_header(value: str) -> str:
    return value.strip().casefold().replace(" ", "").replace("_", "")


def _find_header(headers: dict[str, int], *names: str) -> int | None:
    return next((headers[name] for name in names if name in headers), None)


def _value(row: list[str], index: int | None) -> str:
    return row[index] if index is not None and index < len(row) else ""


def _normalize_type(value: str) -> str | None:
    return {"modem": "modem", "модем": "modem", "tuner": "tuner", "тюнер": "tuner"}.get(value.strip().casefold())


def _normalize_service(value: str) -> str | None:
    return {"internet": "internet", "інтернет": "internet", "television": "television", "телебачення": "television"}.get(value.strip().casefold())
