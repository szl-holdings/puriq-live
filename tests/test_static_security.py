"""Exercise patched static-file behavior without sending expensive attack payloads."""
from importlib.metadata import version
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import app as application

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize("route,source", [
    ("/research", "static/research/index.html"),
    ("/static/research/research.css", "static/research/research.css"),
    ("/static/research/research.js", "static/research/research.js"),
])
def test_static_range_matches_exact_source_bytes(route, source):
    expected = (ROOT / source).read_bytes()
    with TestClient(application.app) as client:
        full = client.get(route)
        part = client.get(route, headers={"Range": "bytes=0-31"})
    assert full.status_code == 200
    assert full.content == expected
    assert part.status_code == 206
    assert part.content == expected[:32]
    assert part.headers["content-range"] == f"bytes 0-31/{len(expected)}"
    assert "content-security-policy" in part.headers


@pytest.mark.parametrize("route", [
    "/static/missing-file.css",
    "/static/%2e%2e/requirements.txt",
    "/static/%5c%5cnot-a-real-host.invalid%5cshare",
])
def test_static_invalid_paths_do_not_return_application_secrets(route):
    with TestClient(application.app) as client:
        response = client.get(route)
    assert response.status_code == 404
    assert b"fastapi==" not in response.content


def test_patched_framework_versions_are_installed_in_the_tested_runtime():
    assert version("fastapi") == "0.141.1"
    assert version("starlette") == "1.6.0"
