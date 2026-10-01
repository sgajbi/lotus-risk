"""Suite-wide isolation for mutable process state on the shared FastAPI test application."""

from collections.abc import Generator

import pytest

from app.main import app


@pytest.fixture(autouse=True)
def reset_shared_app_draining_state() -> Generator[None]:
    """A TestClient lifespan may correctly leave the singleton draining after shutdown.

    Production must retain that shutdown posture. Tests, however, reuse the singleton across
    unrelated cases, so each case starts and ends in the neutral pre-lifespan state.
    """
    app.state.is_draining = False
    yield
    app.state.is_draining = False
