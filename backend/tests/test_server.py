"""Exercise the public API without reading any existing database."""

import os
import uuid
import pytest
from server import create_app, document_value

TOKEN = "synthetic-test-token-not-a-real-secret-0001"


class MemoryStore:
    def __init__(self):
        self.rows = {}

    def ready(self):
        return None

    def list(self):
        return [{"id": key, "document": value} for key, value in self.rows.items()]

    def create(self, identifier, document):
        self.rows[identifier] = document

    def update(self, identifier, document):
        if identifier not in self.rows:
            return False
        self.rows[identifier] = document
        return True

    def delete(self, identifier):
        return self.rows.pop(identifier, None) is not None


@pytest.fixture
def client():
    return create_app(
        {"TESTING": True, "API_ADMIN_TOKEN": TOKEN}, MemoryStore()
    ).test_client()


def test_auth_and_cors(client):
    assert client.get("/api/documents").status_code == 401
    assert (
        client.get(
            "/api/documents", headers={"Origin": "https://evil.test"}
        ).status_code
        == 403
    )
    response = client.options(
        "/api/documents", headers={"Origin": "https://subhashdixit.github.io"}
    )
    assert response.status_code == 204
    assert (
        response.headers["Access-Control-Allow-Origin"]
        == "https://subhashdixit.github.io"
    )


def exercise(client):
    headers = {"Authorization": "Bearer " + TOKEN}
    response = client.post(
        "/api/documents", headers=headers, json={"document": {"name": "Synthetic"}}
    )
    assert response.status_code == 201
    identifier = response.json["id"]
    assert (
        client.get("/api/documents", headers=headers).json["documents"][0]["document"][
            "name"
        ]
        == "Synthetic"
    )
    assert (
        client.put(
            "/api/documents/" + identifier,
            headers=headers,
            json={"document": {"count": 2}},
        ).status_code
        == 200
    )
    assert client.get("/api/documents", headers=headers).json["documents"][0][
        "document"
    ] == {"count": 2}
    assert (
        client.delete("/api/documents/" + identifier, headers=headers).status_code
        == 200
    )
    assert (
        client.delete("/api/documents/" + identifier, headers=headers).status_code
        == 404
    )


def test_crud_contract(client):
    exercise(client)


def test_invalid_inputs_cannot_become_queries(client):
    headers = {"Authorization": "Bearer " + TOKEN}
    assert (
        client.post(
            "/api/documents", headers=headers, json={"document": {"$where": "bad"}}
        ).status_code
        == 400
    )
    assert client.post("/api/documents", headers=headers, json=[]).status_code == 400
    assert (
        client.put(
            "/api/documents/$where", headers=headers, json={"document": {}}
        ).status_code
        == 400
    )
    for value in [{"a.b": 1}, {"nested": {"__proto__": {}}}, {"n": float("nan")}]:
        with pytest.raises(ValueError):
            document_value(value)


def test_missing_configuration_fails_closed():
    client = create_app({"API_ADMIN_TOKEN": "", "MONGODB_URI": ""}).test_client()
    assert client.get("/api/documents").status_code == 503
    assert client.get("/health/ready").json["mongo_configured"] is False


@pytest.mark.skipif(
    not os.environ.get("MONGO_TEST_URI"),
    reason="dedicated Mongo test server not configured",
)
def test_actual_mongo_crud():
    from server import MongoStore

    store = MongoStore(
        os.environ["MONGO_TEST_URI"], "portfolio_ci", "test_" + uuid.uuid4().hex
    )
    try:
        store.ready()
        app = create_app({"API_ADMIN_TOKEN": TOKEN}, store)
        exercise(app.test_client())
        assert store.list() == []
    finally:
        store.collection.drop()
        store.client.close()
