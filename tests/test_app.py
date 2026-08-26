import pytest
from app import app


@pytest.fixture
def client():
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client


def test_home_status_code(client):
    response = client.get('/')
    assert response.status_code == 200


def test_home_response_body(client):
    response = client.get('/')
    data = response.get_json()
    assert data == {"message": "Welcome to the DevOps CI/CD Demo App"}


def test_home_content_type(client):
    response = client.get('/')
    assert response.content_type == 'application/json'


def test_health_status_code(client):
    response = client.get('/health')
    assert response.status_code == 200


def test_health_response_body(client):
    response = client.get('/health')
    data = response.get_json()
    assert data == {"status": "healthy"}


def test_404_not_found(client):
    response = client.get('/does-not-exist')
    assert response.status_code == 404
    data = response.get_json()
    assert data == {"error": "Not found"}


def test_home_only_allows_get(client):
    response = client.post('/')
    assert response.status_code == 405


def test_config_status_reports_missing_key(client, monkeypatch):
    monkeypatch.delenv('API_KEY', raising=False)
    response = client.get('/config-status')
    assert response.status_code == 200
    assert response.get_json() == {"api_key_configured": False}


def test_config_status_reports_present_key(client, monkeypatch):
    monkeypatch.setenv('API_KEY', 'dummy-value-for-testing-only')
    response = client.get('/config-status')
    assert response.status_code == 200
    assert response.get_json() == {"api_key_configured": True}


def test_config_status_never_leaks_key_value(client, monkeypatch):
    secret_value = 'super-secret-value-must-not-appear'
    monkeypatch.setenv('API_KEY', secret_value)
    response = client.get('/config-status')
    assert secret_value not in response.get_data(as_text=True)
