"""Hyderabad market price ingestion.

Sources are pluggable adapters. The default adapters are legal and respectful:
  • ManualCsvSource   — a CSV your purchase team updates (supplier quotes)
  • HttpJsonSource    — any endpoint you are licensed to use (e.g. AGMARKNET open data,
                        Telangana Rythu Bazar published rates, or your BSP partner API)
  • SupplierSheetSource — Google Sheet published as CSV
Never scrape sites that forbid it. Every observation is stored with its source and raw payload.
"""
from __future__ import annotations

import csv
import io
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from typing import Protocol
from uuid import UUID

import httpx

from app.core import db
from app.core.logging import get_logger

log = get_logger("pricing.ingestion")


@dataclass(frozen=True)
class Observation:
    ingredient_key: str
    market: str            # wholesale | retail
    price_per_unit: Decimal
    source: str
    observed_at: datetime
    raw: dict | None = None


class PriceSource(Protocol):
    name: str

    async def fetch(self) -> list[Observation]: ...


class ManualCsvSource:
    """CSV columns: ingredient_key,market,price_per_unit[,observed_at]"""

    name = "manual_csv"

    def __init__(self, csv_text: str, source_label: str = "manual"):
        self.csv_text, self.source_label = csv_text, source_label

    async def fetch(self) -> list[Observation]:
        out = []
        for row in csv.DictReader(io.StringIO(self.csv_text)):
            observed = row.get("observed_at")
            out.append(
                Observation(
                    ingredient_key=row["ingredient_key"].strip(), market=row.get("market", "wholesale").strip(),
                    price_per_unit=Decimal(row["price_per_unit"]), source=self.source_label,
                    observed_at=datetime.fromisoformat(observed) if observed else datetime.now(UTC), raw=dict(row),
                )
            )
        return out


class HttpJsonSource:
    """Expects a JSON array of {ingredient_key, market, price_per_unit, observed_at?}."""

    name = "http_json"

    def __init__(self, url: str, source_label: str, headers: dict | None = None):
        self.url, self.source_label, self.headers = url, source_label, headers or {}

    async def fetch(self) -> list[Observation]:
        async with httpx.AsyncClient(timeout=20) as client:
            r = await client.get(self.url, headers=self.headers)
            r.raise_for_status()
            rows = r.json()
        out = []
        for row in rows:
            out.append(
                Observation(
                    ingredient_key=row["ingredient_key"], market=row.get("market", "wholesale"),
                    price_per_unit=Decimal(str(row["price_per_unit"])), source=self.source_label,
                    observed_at=datetime.fromisoformat(row["observed_at"]) if row.get("observed_at") else datetime.now(UTC),
                    raw=row,
                )
            )
        return out


async def ingest(tenant_id: UUID, sources: list[PriceSource]) -> dict:
    """Write observations, detect alert-worthy moves, refresh cached item costs, bump cache version."""
    from app.core.cache import get_redis
    from app.pricing.repository import refresh_item_costs

    written, alerts = 0, []
    keys = {r["key"]: (r["id"], Decimal(r["alert_threshold_pct"])) for r in await db.fetch(
        "SELECT id, key, alert_threshold_pct FROM ingredients WHERE tenant_id = $1", tenant_id)}
    for src in sources:
        try:
            obs = await src.fetch()
        except Exception as e:  # noqa: BLE001
            log.error("source_failed", source=src.name, error=str(e))
            continue
        async with db.transaction() as conn:
            for o in obs:
                if o.ingredient_key not in keys:
                    continue
                ing_id, threshold = keys[o.ingredient_key]
                prev = await conn.fetchval(
                    "SELECT price_per_unit FROM ingredient_prices WHERE ingredient_id=$1 AND market=$2 ORDER BY observed_at DESC LIMIT 1",
                    ing_id, o.market,
                )
                await conn.execute(
                    "INSERT INTO ingredient_prices (tenant_id, ingredient_id, source, market, price_per_unit, observed_at, raw) VALUES ($1,$2,$3,$4,$5,$6,$7)",
                    tenant_id, ing_id, o.source, o.market, o.price_per_unit, o.observed_at, o.raw,
                )
                written += 1
                if prev and prev > 0:
                    move = (o.price_per_unit - Decimal(prev)) / Decimal(prev) * 100
                    if abs(move) >= threshold:
                        alerts.append({"ingredient": o.ingredient_key, "market": o.market, "move_pct": str(round(move, 2)),
                                       "from": str(prev), "to": str(o.price_per_unit)})
    refreshed = await refresh_item_costs(tenant_id)
    try:
        await get_redis().incr(f"prices_version:{tenant_id}")
    except Exception:  # noqa: BLE001 — cache is best-effort
        pass
    log.info("ingest_done", written=written, alerts=len(alerts), items_refreshed=refreshed)
    return {"written": written, "alerts": alerts, "items_refreshed": refreshed}
