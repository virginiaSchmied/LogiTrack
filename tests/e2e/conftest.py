import os
import pytest

# URL del frontend. Por defecto apunta al servidor local de desarrollo.
# Para correr contra otro entorno: E2E_BASE_URL=http://logi-track.duckdns.org:8080 pytest
BASE_URL = os.environ.get("E2E_BASE_URL", "http://localhost:8080")


@pytest.fixture(scope="session")
def base_url():
    return BASE_URL
