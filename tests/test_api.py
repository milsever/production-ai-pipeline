from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient
from langchain_core.messages import AIMessage

from rag_assistant.api import app

@pytest.fixture
def api_client(monkeypatch):
    """Create a test client with a mocked multi-agent graph."""

    graph = MagicMock()

    graph.invoke.return_value = {
        "routes": ["rag_agent", "application_agent"],
        "messages": [
            AIMessage(content="Test assistant response.")
        ],
    }

    monkeypatch.setattr(
        "rag_assistant.api.build_multi_agent_graph",
        lambda: graph,
    )

    with TestClient(app) as client:
        yield client, graph

def test_health_endpoint(api_client):
    client, _ = api_client

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}

def test_ask_endpoint_success(api_client):
    client, graph = api_client

    response = client.post(
        "/api/v1/ask",
        json={"question": "What are the banking products?"},
    )

    assert response.status_code == 200

    data = response.json()

    assert data["answer"] == "Test assistant response."
    assert data["routes"] == [
        "rag_agent",
        "application_agent",
    ]
    assert data["selected_specialists"] == [
        "RAG Specialist",
        "Application Specialist",
    ]

    graph.invoke.assert_called_once_with({
        "messages": [
            ("user", "What are the banking products?")
        ]
    })

def test_ask_endpoint_strips_question(api_client):
    client, graph = api_client

    response = client.post(
        "/api/v1/ask",
        json={"question": "  What are the fees?  "},
    )

    assert response.status_code == 200

    graph.invoke.assert_called_once_with({
        "messages": [
            ("user", "What are the fees?")
        ]
    })

def test_ask_endpoint_handles_unknown_route(api_client):
    client, graph = api_client

    graph.invoke.return_value = {
        "routes": ["unknown_agent"],
        "messages": [
            AIMessage(content="Test response.")
        ],
    }

    response = client.post(
        "/api/v1/ask",
        json={"question": "Test question"},
    )

    assert response.status_code == 200
    assert response.json()["selected_specialists"] == [
        "unknown_agent"
    ]

def test_ask_endpoint_handles_content_blocks(api_client):
    client, graph = api_client

    graph.invoke.return_value = {
        "routes": ["rag_agent"],
        "messages": [
            AIMessage(content=[
                {"type": "text", "text": "First part."},
                {"type": "text", "text": "Second part."},
            ])
        ],
    }

    response = client.post(
        "/api/v1/ask",
        json={"question": "Test question"},
    )

    assert response.status_code == 200
    assert response.json()["answer"] == (
        "First part.\nSecond part."
    )

@pytest.mark.parametrize(
    "question",
    [
        "",
        "   ",
        "x" * 4001,
    ],
)
def test_ask_endpoint_rejects_invalid_question(
        api_client,
        question,
):
    client, graph = api_client

    response = client.post(
        "/api/v1/ask",
        json={"question": question},
    )

    assert response.status_code == 422
    graph.invoke.assert_not_called()

def test_ask_endpoint_handles_empty_messages(api_client):
    client, graph = api_client

    graph.invoke.return_value = {
        "routes": [],
        "messages": [],
    }

    response = client.post(
        "/api/v1/ask",
        json={"question": "Test question"},
    )

    assert response.status_code == 500
    assert response.json()["detail"] == (
        "An error occurred while processing the request."
    )

def test_ask_endpoint_handles_workflow_exception(api_client):
    client, graph = api_client

    graph.invoke.side_effect = RuntimeError(
        "Internal workflow error"
    )

    response = client.post(
        "/api/v1/ask",
        json={"question": "Test question"},
    )

    assert response.status_code == 500
    assert response.json()["detail"] == (
        "An error occurred while processing the request."
    )

    assert "Internal workflow error" not in response.text
