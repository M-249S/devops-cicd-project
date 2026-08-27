import pytest
import app as app_module
from app import app


@pytest.fixture
def client():
    app.config['TESTING'] = True
    # Reset in-memory state before every test so tests don't leak into
    # each other regardless of execution order.
    app_module._items.clear()
    with app.test_client() as client:
        yield client


def test_list_items_empty(client):
    response = client.get('/items')
    assert response.status_code == 200
    assert response.get_json() == []


def test_create_item_success(client):
    response = client.post('/items', json={"name": "Learn Terraform"})
    assert response.status_code == 201
    data = response.get_json()
    assert data['name'] == "Learn Terraform"
    assert isinstance(data['id'], int)


def test_create_item_missing_name(client):
    response = client.post('/items', json={})
    assert response.status_code == 400
    assert "error" in response.get_json()


def test_create_item_empty_name(client):
    response = client.post('/items', json={"name": "   "})
    assert response.status_code == 400


def test_create_item_no_body(client):
    response = client.post('/items')
    assert response.status_code == 400


def test_create_item_wrong_type(client):
    response = client.post('/items', json={"name": 12345})
    assert response.status_code == 400


def test_list_items_after_create(client):
    client.post('/items', json={"name": "First"})
    client.post('/items', json={"name": "Second"})
    response = client.get('/items')
    assert response.status_code == 200
    data = response.get_json()
    assert len(data) == 2


def test_get_item_success(client):
    created = client.post('/items', json={"name": "Read me"}).get_json()
    response = client.get(f"/items/{created['id']}")
    assert response.status_code == 200
    assert response.get_json() == created


def test_get_item_not_found(client):
    response = client.get('/items/9999')
    assert response.status_code == 404


def test_update_item_success(client):
    created = client.post('/items', json={"name": "Old name"}).get_json()
    response = client.put(f"/items/{created['id']}", json={"name": "New name"})
    assert response.status_code == 200
    assert response.get_json()['name'] == "New name"


def test_update_item_not_found(client):
    response = client.put('/items/9999', json={"name": "Doesn't matter"})
    assert response.status_code == 404


def test_update_item_invalid_body(client):
    created = client.post('/items', json={"name": "Valid"}).get_json()
    response = client.put(f"/items/{created['id']}", json={})
    assert response.status_code == 400


def test_delete_item_success(client):
    created = client.post('/items', json={"name": "Delete me"}).get_json()
    response = client.delete(f"/items/{created['id']}")
    assert response.status_code == 204

    follow_up = client.get(f"/items/{created['id']}")
    assert follow_up.status_code == 404


def test_delete_item_not_found(client):
    response = client.delete('/items/9999')
    assert response.status_code == 404