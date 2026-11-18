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
    "javascript:alert(1)", "http://router.local/", "http://10.0.0.1:80/", "http://2130706433/", "http://0x7f000001/",
])
async def test_blocks_private_or_unsupported_urls(url):
    assert not await service.is_public_url(url)


@pytest.mark.asyncio
@pytest.mark.parametrize("url", ["https://example.com", "http://example.org/path"])
async def test_accepts_public_http_urls(url):
    assert await service.is_public_url(url)


@pytest.mark.parametrize("content_type", [
    "text/html; charset=utf-8",
    "text/plain",
    "application/json",
    "application/xhtml+xml",
])
def test_accepts_readable_content_types(content_type):
    assert service.is_readable_content_type(content_type)


@pytest.mark.parametrize("content_type", [
    "text/css",
    "text/javascript",
    "application/javascript",
    "application/octet-stream",
    "application/pdf",
    "image/png",
    "application/zip",
    "",
])
def test_rejects_binary_or_unknown_content_types(content_type):
    assert not service.is_readable_content_type(content_type)



def test_scroll_action_accepts_bounded_delta():
    action = service.BrowserAction(session_id="a" * 24, action="scroll", delta_y=1200)
    assert action.delta_y == 1200


def test_scroll_action_rejects_unbounded_delta():
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        service.BrowserAction(session_id="a" * 24, action="scroll", delta_y=5000)



@pytest.mark.parametrize(
    ("before", "after", "expected_delta", "expected_scrolled"),
    [
        (0, 700, 700, True),
        (700, 1400, 700, True),
        (1200, 1200, 0, False),
        (900, 200, -700, True),
    ],
)
def test_scroll_evidence_reports_actual_window_movement(before, after, expected_delta, expected_scrolled):
    evidence = service.build_scroll_evidence(700, before, after, "Conteúdo visível")
    assert evidence["requested_delta_y"] == 700
    assert evidence["scroll_y_before"] == before
    assert evidence["scroll_y_after"] == after
    assert evidence["actual_delta_y"] == expected_delta
    assert evidence["scrolled"] is expected_scrolled
    assert evidence["visible_text"] == "Conteúdo visível"


def test_scroll_evidence_limits_visible_text_size():
    evidence = service.build_scroll_evidence(700, 0, 700, "x" * 6000)
    assert len(evidence["visible_text"]) == 5000
