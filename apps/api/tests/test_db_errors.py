import socket

import asyncpg
import pytest

from app.core import db


async def _expect_unreachable(monkeypatch, exc, dsn):
    async def boom(*a, **k):
        raise exc

    monkeypatch.setattr(asyncpg, "create_pool", boom)
    monkeypatch.setattr(db, "_pool", None)
    monkeypatch.setenv("DATABASE_URL", dsn)
    db.get_settings.cache_clear()
    with pytest.raises(db.DatabaseUnreachable) as e:
        await db.init_pool()
    db.get_settings.cache_clear()
    return str(e.value)


async def test_unresolvable_host_names_the_host_and_the_check(monkeypatch):
    msg = await _expect_unreachable(
        monkeypatch, socket.gaierror(-2, "Name or service not known"),
        "postgresql://u:p@ep-typo.aws.neon.tech/neondb?sslmode=require",
    )
    assert "ep-typo.aws.neon.tech" in msg
    assert "doctor" in msg
    assert "u:p" not in msg.split("\n")[0]  # the password is not echoed on the headline


async def test_refused_connection_suggests_starting_docker(monkeypatch):
    msg = await _expect_unreachable(monkeypatch, ConnectionRefusedError(111, "refused"), "postgresql://hecai:hecai@localhost:5432/hecai")
    assert "localhost:5432" in msg and "docker compose" in msg


async def test_bad_credentials_are_reported_as_credentials(monkeypatch):
    msg = await _expect_unreachable(monkeypatch, asyncpg.InvalidPasswordError("nope"), "postgresql://u:p@ep-x.aws.neon.tech/neondb")
    assert "rejected the username or password" in msg


async def test_prod_with_default_localhost_says_the_variable_is_missing(monkeypatch):
    monkeypatch.setenv("APP_ENV", "prod")
    msg = await _expect_unreachable(monkeypatch, ConnectionRefusedError(111, "refused"), "postgresql://hecai:hecai@localhost:5432/hecai")
    assert "DATABASE_URL is not set" in msg and "variables" in msg


async def test_dev_with_localhost_still_suggests_docker(monkeypatch):
    monkeypatch.setenv("APP_ENV", "dev")
    msg = await _expect_unreachable(monkeypatch, ConnectionRefusedError(111, "refused"), "postgresql://hecai:hecai@localhost:5432/hecai")
    assert "docker compose" in msg
