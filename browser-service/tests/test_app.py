import asyncio
import pytest

from app import is_public_url


@pytest.mark.asyncio
@pytest.mark.parametrize("url", [
    "http://127.0.0.1/", "http://localhost/", "http://192.168.1.1/",
    "http://169.254.169.254/latest/meta-data/", "file:///etc/passwd",
    "javascript:alert(1)", "http://router.local/", "http://10.0.0.1:80/",
])
async def test_blocks_private_or_unsupported_urls(url):
    assert not await is_public_url(url)


@pytest.mark.asyncio
@pytest.mark.parametrize("url", ["https://example.com", "http://example.org/path"])
async def test_accepts_public_http_urls(url):
    assert await is_public_url(url)
