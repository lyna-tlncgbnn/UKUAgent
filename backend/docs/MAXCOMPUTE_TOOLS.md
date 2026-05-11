# MaxCompute Tools

UkuBot can expose Alibaba Cloud MaxCompute as read-only agent tools. The first version supports table discovery, schema inspection, small table samples, and bounded SELECT queries. It does not provide table creation, writes, deletion, resource management, UDF, or authorization tools.

## Environment

Configure credentials and project settings in `.env`:

```bash
ALIBABA_CLOUD_ACCESS_KEY_ID=your-access-key-id
ALIBABA_CLOUD_ACCESS_KEY_SECRET=your-access-key-secret
MAXCOMPUTE_PROJECT=your-maxcompute-project
MAXCOMPUTE_ENDPOINT=https://service.cn-hangzhou.maxcompute.aliyun.com/api

# Optional
MAXCOMPUTE_SCHEMA=your-schema
MAXCOMPUTE_DEFAULT_LIMIT=100
MAXCOMPUTE_QUERY_TIMEOUT_SECONDS=120
```

Do not hard-code AccessKey values in scripts or tool modules. If credentials were shared in logs or chat, rotate them before long-running use.

## Config

Add the `maxcompute` group and enable the tools in `config.yaml`:

```yaml
tool_groups:
  - name: maxcompute

tools:
  - name: maxcompute_list_tables
    group: maxcompute
    use: deerflow.community.maxcompute.tools:maxcompute_list_tables_tool

  - name: maxcompute_describe_table
    group: maxcompute
    use: deerflow.community.maxcompute.tools:maxcompute_describe_table_tool

  - name: maxcompute_sample_table
    group: maxcompute
    use: deerflow.community.maxcompute.tools:maxcompute_sample_table_tool

  - name: maxcompute_query
    group: maxcompute
    use: deerflow.community.maxcompute.tools:maxcompute_query_tool
```

## Available Tools

- `maxcompute_list_tables(prefix=None, limit=20)`: lists visible MaxCompute tables.
- `maxcompute_describe_table(table_name)`: returns table metadata, regular columns, and partition columns.
- `maxcompute_sample_table(table_name, limit=20, partition=None)`: returns a small sample from a table.
- `maxcompute_query(sql, limit=100)`: runs one bounded read-only `SELECT` or `WITH` query.

All tools return JSON strings so the agent can parse results reliably.

## Safety

The v1 surface is strictly read-only. `maxcompute_query` rejects multi-statement SQL and blocks high-risk keywords such as `insert`, `update`, `delete`, `drop`, `create`, `alter`, `truncate`, `merge`, `grant`, and `revoke`.

Query results are bounded. The default result limit is `MAXCOMPUTE_DEFAULT_LIMIT` or 100 rows, and the hard maximum is 1000 rows.
