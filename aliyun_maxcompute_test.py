"""Read-only Alibaba Cloud MaxCompute connection smoke test.

Fill these values in `.env` or your shell before running:

  ALIBABA_CLOUD_ACCESS_KEY_ID=...
  ALIBABA_CLOUD_ACCESS_KEY_SECRET=...
  MAXCOMPUTE_PROJECT=your_project_name
  MAXCOMPUTE_ENDPOINT=https://service.cn-hangzhou.maxcompute.aliyun.com/api

Optional:

  MAXCOMPUTE_SCHEMA=your_schema_name
  MAXCOMPUTE_TABLE_LIMIT=5
  MAXCOMPUTE_RUN_SQL=1
  MAXCOMPUTE_TEST_SQL="select 1 as ok;"

Install dependency if needed:

  pip install pyodps python-dotenv
"""

from __future__ import annotations

import os
from itertools import islice
from typing import Any

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover - convenience fallback
    load_dotenv = None

try:
    from odps import ODPS
except ImportError as exc:  # pragma: no cover - dependency smoke test
    raise SystemExit(
        "Missing dependency: pyodps. Install it with:\n"
        "  pip install pyodps python-dotenv"
    ) from exc


if load_dotenv is not None:
    load_dotenv()


def _required_env() -> dict[str, str]:
    values = {
        "ALIBABA_CLOUD_ACCESS_KEY_ID": os.getenv("ALIBABA_CLOUD_ACCESS_KEY_ID", "").strip(),
        "ALIBABA_CLOUD_ACCESS_KEY_SECRET": os.getenv("ALIBABA_CLOUD_ACCESS_KEY_SECRET", "").strip(),
        "MAXCOMPUTE_PROJECT": os.getenv("MAXCOMPUTE_PROJECT", "").strip(),
        "MAXCOMPUTE_ENDPOINT": os.getenv("MAXCOMPUTE_ENDPOINT", "").strip().rstrip("/"),
    }
    missing = [name for name, value in values.items() if not value]
    if missing:
        raise SystemExit(f"Missing required environment variables: {', '.join(missing)}")
    return values


def _safe_table_summary(table: Any) -> dict[str, Any]:
    return {
        "name": getattr(table, "name", None),
        "schema": getattr(table, "schema", None),
        "creation_time": str(getattr(table, "creation_time", "") or ""),
        "last_modified_time": str(getattr(table, "last_modified_time", "") or ""),
    }


def main() -> None:
    env = _required_env()
    schema = os.getenv("MAXCOMPUTE_SCHEMA", "").strip() or None
    table_limit = int(os.getenv("MAXCOMPUTE_TABLE_LIMIT", "5"))
    run_sql = os.getenv("MAXCOMPUTE_RUN_SQL", "").strip().lower() in {"1", "true", "yes", "on"}
    test_sql = os.getenv("MAXCOMPUTE_TEST_SQL", "select 1 as ok;").strip()

    client = ODPS(
        access_id=env["ALIBABA_CLOUD_ACCESS_KEY_ID"],
        secret_access_key=env["ALIBABA_CLOUD_ACCESS_KEY_SECRET"],
        project=env["MAXCOMPUTE_PROJECT"],
        endpoint=env["MAXCOMPUTE_ENDPOINT"],
        schema=schema,
    )

    print("Connecting to MaxCompute...")
    print(
        {
            "project": env["MAXCOMPUTE_PROJECT"],
            "endpoint": env["MAXCOMPUTE_ENDPOINT"],
            "schema": schema,
            "accessKeyIdPrefix": env["ALIBABA_CLOUD_ACCESS_KEY_ID"][:4] + "***",
        }
    )

    project = client.get_project()
    print("Connection succeeded.")
    print(
        {
            "projectName": getattr(project, "name", env["MAXCOMPUTE_PROJECT"]),
            "owner": getattr(project, "owner", None),
            "comment": getattr(project, "comment", None),
        }
    )

    print(f"Listing up to {table_limit} tables...")
    tables = [_safe_table_summary(table) for table in islice(client.list_tables(), table_limit)]
    print({"tableCountShown": len(tables), "tables": tables})

    if not run_sql:
        print("SQL test skipped. Set MAXCOMPUTE_RUN_SQL=1 to run a read-only SQL smoke test.")
        return

    print(f"Running SQL smoke test: {test_sql}")
    instance = client.execute_sql(test_sql)
    instance.wait_for_success()
    with instance.open_reader() as reader:
        rows = [list(row.values) for row in islice(reader, 5)]
    print({"sqlSucceeded": True, "rows": rows})


if __name__ == "__main__":
    main()
