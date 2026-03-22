from fastapi.testclient import TestClient
import os
import io
from app.main import app

client = TestClient(app)

def test_api_status():
    """Verify OpenAPI and API works"""
    # Just checking frontend index exists locally over route
    response = client.get("/")
    assert response.status_code == 200

def test_upload_missing_file():
    """Tenta upload sem arquivo e espera erro OWASP seguro 422/400"""
    response = client.post("/api/v1/upload-video")
    # FastAPI returns 422 if missing field File()
    assert response.status_code == 422

def test_upload_invalid_extension():
    """Mock invalid payload to verify validation trigger"""
    # Create fake malicious payload
    file_content = b"fake virus payload"
    file_name = "malicious.js"
    
    response = client.post(
        "/api/v1/upload-video",
        files={"file": (file_name, file_content, "application/javascript")}
    )
    
    # Must fail securely
    assert response.status_code == 400
    assert "permitida" in response.json()["detail"].lower()
