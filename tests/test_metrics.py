import pytest
from app import app


@pytest.fixture
def client():
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client


def test_metrics_status_code(client):
    response = client.get('/metrics')
    assert response.status_code == 200


def test_metrics_content_type(client):
    response = client.get('/metrics')
    assert 'text/plain' in response.content_type


def test_metrics_tracks_requests(client):
    client.get('/health')
    response = client.get('/metrics')
    body = response.get_data(as_text=True)

    assert 'http_requests_total' in body
    assert 'endpoint="health"' in body


def test_metrics_tracks_latency(client):
    client.get('/health')
    response = client.get('/metrics')
    body = response.get_data(as_text=True)

    assert 'http_request_duration_seconds' in body


def test_metrics_endpoint_itself_not_double_counted(client):
    # Calling /metrics should not inflate its own request count, since
    # that would make the metric endpoint self-referential and noisy.
    client.get('/metrics')
    response = client.get('/metrics')
    body = response.get_data(as_text=True)

    assert 'endpoint="metrics"' not in body
