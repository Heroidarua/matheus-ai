import importlib.util
import sys
from pathlib import Path

import pytest


MODULE_PATH = Path(__file__).resolve().parents[1] / "app.py"
SPEC = importlib.util.spec_from_file_location("ada_browser_service_app", MODULE_PATH)
service = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
sys.modules[SPEC.name] = service
SPEC.loader.exec_module(service)


@pytest.mark.asyncio
@pytest.mark.parametrize("url", [
    "http://127.0.0.1/", "http://localhost/", "http://192.168.1.1/",
    "http://169.254.169.254/latest/meta-data/", "file:///etc/passwd",
    "javascript:alert(1)", "http://router.local/", "http://10.0.0.1:80/",
])
async def test_blocks_private_or_unsupported_urls(url):
    assert not await service.is_public_url(url)


@pytest.mark.asyncio
@pytest.mark.parametrize("url", ["https://example.com", "http://example.org/path"])
async def test_accepts_public_http_urls(url):
    assert await service.is_public_url(url)
