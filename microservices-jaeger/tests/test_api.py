import requests

def test_login():
    response = requests.post("http://localhost:8080/api/login", json={"username": "user", "password": "pass"})
    assert response.status_code == 200
    assert response.json() == {"username": "user", "profile": {"name": "Test User", "email": "user@example.com"}}