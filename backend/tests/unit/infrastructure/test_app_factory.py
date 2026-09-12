"""Unit tests for the application factory."""

import pytest
from fastapi import APIRouter, FastAPI
from httpx import ASGITransport, AsyncClient

from src.infrastructure import app_factory
from src.infrastructure.auth.dependencies import get_current_superuser
from src.infrastructure.config.settings import EnvironmentOption, Settings, settings

DOCS_PATHS = ("/docs", "/redoc", "/openapi.json")


@pytest.mark.asyncio
async def test_startup_failure_surfaces_the_original_error(monkeypatch):
    """A failed startup must raise the failing step's exception, not a teardown one."""

    async def failing_create_tables() -> None:
        raise RuntimeError("db unreachable")

    monkeypatch.setattr(app_factory, "create_tables", failing_create_tables)

    lifespan = app_factory.lifespan_factory(settings, create_tables_on_startup=True)

    with pytest.raises(RuntimeError, match="db unreachable"):
        async with lifespan(FastAPI()):
            pass  # pragma: no cover - startup fails before the yield


def _create_app(environment: EnvironmentOption, enable_docs_in_production: bool = False) -> FastAPI:
    return app_factory.create_application(
        router=APIRouter(),
        settings=Settings(ENVIRONMENT=environment, ENABLE_DOCS_IN_PRODUCTION=enable_docs_in_production),
    )


async def _docs_statuses(app: FastAPI) -> list[int]:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        return [(await client.get(path)).status_code for path in DOCS_PATHS]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("environment", "enable_docs_in_production", "expected_status"),
    [
        (EnvironmentOption.LOCAL, False, 200),
        (EnvironmentOption.DEVELOPMENT, False, 200),
        (EnvironmentOption.STAGING, False, 401),
        (EnvironmentOption.PRODUCTION, False, 404),
        (EnvironmentOption.PRODUCTION, True, 401),
    ],
)
async def test_docs_access_for_anonymous_requests(environment, enable_docs_in_production, expected_status):
    app = _create_app(environment, enable_docs_in_production)

    assert await _docs_statuses(app) == [expected_status] * len(DOCS_PATHS)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("environment", "enable_docs_in_production"),
    [(EnvironmentOption.STAGING, False), (EnvironmentOption.PRODUCTION, True)],
)
async def test_gated_docs_are_served_to_superusers(environment, enable_docs_in_production):
    app = _create_app(environment, enable_docs_in_production)
    app.dependency_overrides[get_current_superuser] = lambda: {"id": 1, "is_superuser": True}

    assert await _docs_statuses(app) == [200] * len(DOCS_PATHS)
