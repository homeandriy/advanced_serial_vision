from __future__ import annotations

from collections.abc import Sequence
from typing import TypedDict


class ObjectSchema(TypedDict, total=False):
    type: str
    required: list[str]
    properties: dict[str, object]


class ApiOperation(TypedDict, total=False):
    tags: list[str]
    summary: str
    description: str
    parameters: Sequence[dict[str, object]]
    requestBody: dict[str, object]
    responses: dict[str, object]
    security: list[dict[str, object]]


class ApiPathItem(TypedDict, total=False):
    get: ApiOperation
    post: ApiOperation
    patch: ApiOperation
    delete: ApiOperation


class ImportSummary(TypedDict):
    added: int
    duplicates: int
    invalid_rows: Sequence[str]


class StatisticsSummary(TypedDict):
    operations: dict[str, dict[str, int]]
    services: dict[str, int]
    models: dict[str, int]
