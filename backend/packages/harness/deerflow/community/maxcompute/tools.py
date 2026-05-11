"""Read-only Alibaba Cloud MaxCompute tools for DeerFlow.

The v1 tool surface intentionally exposes metadata reads and bounded SELECT
queries only. It does not provide tools for creating, updating, or deleting
MaxCompute objects.
"""

from __future__ import annotations

import json
import logging
import os
import re
import time
from collections.abc import Iterable
from datetime import date, datetime
from decimal import Decimal
from itertools import islice
from typing import Any

from dotenv import load_dotenv
from langchain.tools import tool
from odps import ODPS

logger = logging.getLogger(__name__)

load_dotenv()

DEFAULT_LIMIT = 100
MAX_LIMIT = 1000
DEFAULT_TIMEOUT_SECONDS = 120
FORBIDDEN_SQL_KEYWORDS = {
    "insert",
    "update",
    "delete",
    "drop",
    "create",
    "alter",
    "truncate",
    "merge",
    "grant",
    "revoke",
    "put",
    "add",
    "remove",
}


class MaxComputeConfigError(RuntimeError):
    """Raised when MaxCompute environment configuration is incomplete."""


class MaxComputeSafetyError(RuntimeError):
    """Raised when a query violates the read-only safety policy."""


def _json(data: dict[str, Any]) -> str:
    return json.dumps(data, ensure_ascii=False, indent=2, default=_json_default)


def _json_default(value: Any) -> str:
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    return str(value)


def _bounded_limit(limit: int | None, *, default: int = DEFAULT_LIMIT) -> int:
    if limit is None:
        limit = default
    return max(1, min(int(limit), MAX_LIMIT))


def _get_env_int(name: str, default: int) -> int:
    raw = os.getenv(name, "").strip()
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def _get_config() -> dict[str, str | None]:
    config: dict[str, str | None] = {
        "access_id": os.getenv("ALIBABA_CLOUD_ACCESS_KEY_ID", "").strip(),
        "secret_access_key": os.getenv("ALIBABA_CLOUD_ACCESS_KEY_SECRET", "").strip(),
        "project": os.getenv("MAXCOMPUTE_PROJECT", "").strip(),
        "endpoint": os.getenv("MAXCOMPUTE_ENDPOINT", "").strip().rstrip("/"),
        "schema": os.getenv("MAXCOMPUTE_SCHEMA", "").strip() or None,
    }
    missing = [
        env_name
        for env_name, value in {
            "ALIBABA_CLOUD_ACCESS_KEY_ID": config["access_id"],
            "ALIBABA_CLOUD_ACCESS_KEY_SECRET": config["secret_access_key"],
            "MAXCOMPUTE_PROJECT": config["project"],
            "MAXCOMPUTE_ENDPOINT": config["endpoint"],
        }.items()
        if not value
    ]
    if missing:
        raise MaxComputeConfigError(f"Missing required environment variables: {', '.join(missing)}")
    return config


def _client() -> ODPS:
    config = _get_config()
    return ODPS(
        access_id=str(config["access_id"]),
        secret_access_key=str(config["secret_access_key"]),
        project=str(config["project"]),
        endpoint=str(config["endpoint"]),
        schema=config["schema"],
    )


def _error(endpoint: str, exc: Exception) -> str:
    config: dict[str, str | None]
    try:
        config = _get_config()
    except Exception:
        config = {"project": os.getenv("MAXCOMPUTE_PROJECT", "").strip() or None, "endpoint": os.getenv("MAXCOMPUTE_ENDPOINT", "").strip() or None}
    return _json(
        {
            "error": True,
            "endpoint": endpoint,
            "project": config.get("project"),
            "maxcomputeEndpoint": config.get("endpoint"),
            "message": f"{type(exc).__name__}: {exc}",
        }
    )


def _safe_get(obj: Any, name: str, default: Any = None) -> Any:
    try:
        return getattr(obj, name, default)
    except Exception:
        return default


def _column_summary(column: Any) -> dict[str, Any]:
    return {
        "name": _safe_get(column, "name"),
        "type": str(_safe_get(column, "type", "")),
        "comment": _safe_get(column, "comment"),
        "nullable": _safe_get(column, "nullable"),
    }


def _table_summary(table: Any) -> dict[str, Any]:
    return {
        "name": _safe_get(table, "name"),
        "type": _safe_get(table, "type"),
        "isVirtualView": bool(_safe_get(table, "is_virtual_view", False) or _safe_get(table, "is_view", False)),
        "comment": _safe_get(table, "comment"),
        "owner": _safe_get(table, "owner"),
        "creationTime": _safe_get(table, "creation_time"),
        "lastDataModifiedTime": _safe_get(table, "last_data_modified_time", _safe_get(table, "last_modified_time")),
    }


def _describe_table_payload(table: Any) -> dict[str, Any]:
    table_schema = _safe_get(table, "table_schema")
    columns = list(_safe_get(table_schema, "columns", []) or [])
    partitions = list(_safe_get(table_schema, "partitions", []) or [])
    return {
        **_table_summary(table),
        "size": _safe_get(table, "size"),
        "lifecycle": _safe_get(table, "lifecycle"),
        "columns": [_column_summary(column) for column in columns],
        "partitions": [_column_summary(column) for column in partitions],
    }


def _record_values(record: Any) -> list[Any]:
    values = _safe_get(record, "values")
    if values is not None:
        return list(values)
    if isinstance(record, dict):
        return list(record.values())
    try:
        return list(record)
    except TypeError:
        return [record]


def _validate_table_identifier(table_name: str) -> str:
    table_name = table_name.strip()
    if not re.match(r"^[A-Za-z_][A-Za-z0-9_]*(\.[A-Za-z_][A-Za-z0-9_]*)?$", table_name):
        raise MaxComputeSafetyError("Invalid table name. Only simple table or schema.table identifiers are allowed.")
    return table_name


def _reader_columns(reader: Any, first_row: Any | None = None) -> list[str]:
    schema = _safe_get(reader, "schema") or _safe_get(reader, "_schema")
    columns = list(_safe_get(schema, "columns", []) or [])
    names = [_safe_get(column, "name") for column in columns if _safe_get(column, "name")]
    if names:
        return names
    if first_row is not None:
        row_columns = _safe_get(first_row, "_columns")
        if row_columns:
            return [str(column) for column in row_columns]
        row_values = _record_values(first_row)
        return [f"col_{index + 1}" for index in range(len(row_values))]
    return []


def _rows_payload(records: Iterable[Any], limit: int, columns: list[str] | None = None) -> tuple[list[str], list[dict[str, Any]]]:
    materialized = list(islice(records, limit))
    if columns is None:
        columns = _reader_columns(None, materialized[0] if materialized else None)
    rows = []
    for record in materialized:
        values = _record_values(record)
        if len(columns) < len(values):
            columns = [*columns, *[f"col_{index + 1}" for index in range(len(columns), len(values))]]
        rows.append({columns[index]: values[index] for index in range(min(len(columns), len(values)))})
    return columns, rows


def _strip_sql_comments(sql: str) -> str:
    sql = re.sub(r"/\*.*?\*/", " ", sql, flags=re.S)
    sql = re.sub(r"--[^\n\r]*", " ", sql)
    return sql.strip()


def _validate_read_only_sql(sql: str) -> str:
    cleaned = _strip_sql_comments(sql).strip()
    if not cleaned:
        raise MaxComputeSafetyError("SQL is required.")

    normalized = cleaned.rstrip(";").strip()
    if ";" in normalized:
        raise MaxComputeSafetyError("Only one SQL statement is allowed.")

    if not re.match(r"^(select|with)\b", normalized, flags=re.I):
        raise MaxComputeSafetyError("Only read-only SELECT or WITH queries are allowed.")

    lowered = normalized.lower()
    for keyword in FORBIDDEN_SQL_KEYWORDS:
        if re.search(rf"\b{re.escape(keyword)}\b", lowered):
            raise MaxComputeSafetyError(f"Forbidden SQL keyword: {keyword}")
    return normalized


def _logview(instance: Any) -> str | None:
    for method_name in ("get_logview_address", "get_logview_url"):
        method = _safe_get(instance, method_name)
        if callable(method):
            try:
                return method()
            except Exception:
                continue
    return None


def _read_instance_rows(instance: Any, limit: int) -> tuple[list[str], list[dict[str, Any]]]:
    with instance.open_reader(tunnel=True, limit=True) as reader:
        rows_raw = list(islice(reader, limit))
        columns = _reader_columns(reader, rows_raw[0] if rows_raw else None)
        return _rows_payload(rows_raw, limit, columns)


@tool("maxcompute_list_tables", parse_docstring=True)
def maxcompute_list_tables_tool(prefix: str | None = None, limit: int = 20) -> str:
    """List visible MaxCompute tables.

    Args:
        prefix: Optional table-name prefix filter.
        limit: Maximum number of tables to return. Default is 20.
    """
    limit = _bounded_limit(limit, default=20)
    try:
        odps = _client()
        tables = odps.list_tables(prefix=prefix or None, extended=True)
        results = [_table_summary(table) for table in islice(tables, limit)]
        return _json({"prefix": prefix, "limit": limit, "totalResults": len(results), "tables": results})
    except Exception as exc:
        logger.warning("MaxCompute list tables failed: %s", exc)
        return _error("maxcompute_list_tables", exc)


@tool("maxcompute_describe_table", parse_docstring=True)
def maxcompute_describe_table_tool(table_name: str) -> str:
    """Describe a MaxCompute table schema and metadata.

    Args:
        table_name: MaxCompute table name.
    """
    if not table_name.strip():
        return _json({"error": True, "endpoint": "maxcompute_describe_table", "message": "table_name is required."})
    try:
        table = _client().get_table(table_name.strip())
        return _json(_describe_table_payload(table))
    except Exception as exc:
        logger.warning("MaxCompute describe table failed: %s", exc)
        return _error("maxcompute_describe_table", exc)


@tool("maxcompute_sample_table", parse_docstring=True)
def maxcompute_sample_table_tool(table_name: str, limit: int = 20, partition: str | None = None) -> str:
    """Read a small sample from a MaxCompute table.

    Args:
        table_name: MaxCompute table name.
        limit: Maximum number of rows to return. Default is 20.
        partition: Optional partition spec, such as ds=20260511.
    """
    limit = _bounded_limit(limit, default=20)
    if not table_name.strip():
        return _json({"error": True, "endpoint": "maxcompute_sample_table", "message": "table_name is required."})
    try:
        odps = _client()
        safe_table_name = _validate_table_identifier(table_name)
        table = odps.get_table(safe_table_name)
        try:
            records = table.head(limit, partition=partition)
        except Exception:
            if partition:
                raise
            instance = odps.execute_sql(f"select * from {safe_table_name} limit {limit}")
            instance.wait_for_success(timeout=_get_env_int("MAXCOMPUTE_QUERY_TIMEOUT_SECONDS", DEFAULT_TIMEOUT_SECONDS))
            columns, rows = _read_instance_rows(instance, limit)
            return _json(
                {
                    "tableName": safe_table_name,
                    "partition": partition,
                    "limit": limit,
                    "rowCount": len(rows),
                    "columns": columns,
                    "rows": rows,
                    "fallback": "select_limit",
                    "logView": _logview(instance),
                }
            )
        schema = _safe_get(table, "table_schema")
        columns = [_safe_get(column, "name") for column in list(_safe_get(schema, "columns", []) or [])]
        columns, rows = _rows_payload(records, limit, [name for name in columns if name])
        return _json(
            {
                "tableName": safe_table_name,
                "partition": partition,
                "limit": limit,
                "rowCount": len(rows),
                "columns": columns,
                "rows": rows,
            }
        )
    except Exception as exc:
        logger.warning("MaxCompute sample table failed: %s", exc)
        return _error("maxcompute_sample_table", exc)


@tool("maxcompute_query", parse_docstring=True)
def maxcompute_query_tool(sql: str, limit: int | None = None) -> str:
    """Run a bounded read-only MaxCompute SQL query.

    Args:
        sql: A single SELECT or WITH SQL statement.
        limit: Maximum number of rows to return. Default is MAXCOMPUTE_DEFAULT_LIMIT or 100.
    """
    default_limit = _get_env_int("MAXCOMPUTE_DEFAULT_LIMIT", DEFAULT_LIMIT)
    timeout = _get_env_int("MAXCOMPUTE_QUERY_TIMEOUT_SECONDS", DEFAULT_TIMEOUT_SECONDS)
    limit = _bounded_limit(limit, default=default_limit)
    try:
        safe_sql = _validate_read_only_sql(sql)
        started = time.monotonic()
        instance = _client().execute_sql(safe_sql)
        instance.wait_for_success(timeout=timeout)
        logview = _logview(instance)
        columns, rows = _read_instance_rows(instance, limit)
        elapsed_ms = int((time.monotonic() - started) * 1000)
        return _json(
            {
                "sqlSucceeded": True,
                "limit": limit,
                "rowCount": len(rows),
                "elapsedMs": elapsed_ms,
                "logView": logview,
                "columns": columns,
                "rows": rows,
            }
        )
    except (MaxComputeConfigError, MaxComputeSafetyError) as exc:
        return _error("maxcompute_query", exc)
    except Exception as exc:
        logger.warning("MaxCompute query failed: %s", exc)
        return _error("maxcompute_query", exc)
