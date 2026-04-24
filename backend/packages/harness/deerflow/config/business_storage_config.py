from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class BusinessStorageConfig(BaseModel):
    """Configuration for business metadata persistence."""

    enabled: bool = Field(default=False, description="Whether to enable the business metadata storage layer.")
    connection_string: str = Field(
        default="sqlite+aiosqlite:///./.deer-flow/business.db",
        description=(
            "SQLAlchemy async connection string for business metadata. "
            "Examples: 'sqlite+aiosqlite:///./.deer-flow/business.db' or "
            "'postgresql+psycopg://user:pass@host:5432/dbname'."
        ),
    )
    auto_create_tables: bool = Field(default=True, description="Whether to create missing business metadata tables at startup.")
    echo: bool = Field(default=False, description="Whether to enable SQL echo logging for the business database.")

    model_config = ConfigDict(extra="forbid")
