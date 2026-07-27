from fastapi.testclient import TestClient

from app.main import app, store

client = TestClient(app)


def setup_function():
    store._holdings.clear()  # Isolate in-memory MVP tests.


def test_health():
    assert client.get("/health").json() == {"status": "ok"}


def test_glossary():
    response = client.get("/v1/glossary/%E5%9B%9E%E8%B4%AD")
    assert response.status_code == 200
    assert response.json()["term"] == "回购"


def test_holding_lifecycle_and_feed():
    created = client.post("/v1/holdings", json={"symbol": "01810", "name": "小米集团-W", "quantity": 100, "average_cost": 45.5})
    assert created.status_code == 201
    holding_id = created.json()["id"]
    assert client.get("/v1/holdings").json()[0]["symbol"] == "01810"
    assert client.get("/v1/feed").json()[0]["related_symbols"] == ["01810"]
    assert client.delete(f"/v1/holdings/{holding_id}").status_code == 204


def test_import_accepts_valid_rows_and_rejects_invalid_rows():
    content = "symbol,name,quantity,average_cost\n600519,贵州茅台,10,1450\nbad,错误,0,4"
    response = client.post("/v1/holdings/import", params={"csv_content": content})
    assert response.status_code == 200
    assert response.json()["accepted"] == 1
    assert response.json()["rejected_rows"] == [3]


def test_import_rejects_unknown_header():
    response = client.post("/v1/holdings/import", params={"csv_content": "code,name\n1,a"})
    assert response.status_code == 422
