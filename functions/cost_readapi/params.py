"""Query parameter parsing and validation for the read API."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict

Panel = Literal[
    "kpis",
    "trend",
    "by_category",
    "by_resource_group",
    "changes",
    "email_summary",
    "budget_status",
]
Range = Literal["this_month", "mtd", "last_7", "last_30", "last_90", "all"]
Granularity = Literal["daily", "weekly", "monthly"]
CostType = Literal["amortized", "actual"]


class Query(BaseModel):
    """Validated dashboard query parameters."""

    model_config = ConfigDict(extra="ignore")

    panel: Panel = "trend"
    range: Range = "last_30"
    granularity: Granularity = "weekly"
    cost_type: CostType = "amortized"
    subscription: str | None = None
    resource_group: str | None = None
    category: str | None = None
    budget: float | None = None


def parse_query(params: dict[str, str]) -> Query:
    """Parse and validate a query-string mapping into a Query.

    Args:
        params: Raw query-string key/value pairs.

    Returns:
        A validated Query (raises pydantic.ValidationError on bad input).
    """
    cleaned = {key: value for key, value in params.items() if value not in (None, "")}
    return Query.model_validate(cleaned)
