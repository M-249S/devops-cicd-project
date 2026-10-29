import pytest

from app import app

EXPECTED = {
    "X-Content-Type-Options": "nosniff",
    "Cross-Origin-Resource-Policy": "same-origin",
    "Cache-Control": "no-store",
    "X-Frame-Options": "DENY",
}


@pytest.fixture
def client():
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


@pytest.mark.parametrize("path", ["/", "/health", "/items", "/does-not-exist"])
def test_security_headers_present(client, path):
    response = client.get(path)
    for header, value in EXPECTED.items():
        assert response.headers.get(header) == value, f"{header} wrong on {path}"
    assert "default-src 'none'" in response.headers.get("Content-Security-Policy", "")
    assert "Permissions-Policy" in response.headers
