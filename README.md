[![CI/CD](https://github.com/milsever/production-ai-pipeline/actions/workflows/ci.yml/badge.svg)](https://github.com/milsever/production-ai-pipeline/actions/workflows/ci.yml)

# Production AI Service & MLOps

A production-oriented multi-agent AI service built with **Python, FastAPI, LangGraph, Docker, Prometheus, Grafana, and Microsoft Azure**.

This project is the third stage of a GenAI engineering project series, evolving an enterprise RAG assistant into a containerized, monitored, and cloud-deployable AI service.

## Project Evolution

This project builds upon two previous projects:

| Project | Focus |
|---|---|
| [Enterprise RAG Assistant](https://github.com/milsever/enterprise-rag-assistant) | Enterprise knowledge retrieval using RAG |
| [Agentic AI Workflow](https://github.com/milsever/agentic-ai-workflow) | Multi-agent orchestration and tool calling |
| **Production AI Service & MLOps** | API integration, containerization, monitoring, CI/CD, and cloud deployment |

The third project focuses on taking the multi-agent architecture further towards production deployment and operational reliability.

## Application Architecture

The system uses a LangGraph orchestrator to route requests to specialized agents:

- **RAG Specialist:** Retrieves information from enterprise documents using ChromaDB and hybrid retrieval.
- **Application Specialist:** Queries a mock customer application API.
- **Orchestrator:** Coordinates the specialists and generates the final response.

```text
                         User
                          |
                    FastAPI / CLI
                          |
                  LangGraph Orchestrator
                     /           \
               RAG Agent    Application Agent
                   |                |
               ChromaDB        Customer API
```

## Deployment Architecture

The same application codebase supports local Docker Compose execution and cloud deployment to Microsoft Azure Container Apps.

### Local environment

```text
                 Docker Compose
                       |
        +--------------+----------------+
        |              |                |
    AI Service    Customer API      Monitoring
        |                             stack
    ChromaDB                    +----------------+
                                | Prometheus      |
                                | Grafana         |
                                | cAdvisor        |
                                +----------------+
```

### Microsoft Azure environment

```text
                    Public HTTPS ingress
                            |
                       AI Service
                   Azure Container Apps
                            |
                 Internal service connection
                            |
                      Customer API
                   Azure Container Apps

              Both apps use images from ACR
```

- **Azure Container Registry (ACR):** Stores versioned application container images.
- **Azure Container Apps:** Hosts the public AI Service and the Customer API with internal ingress.
- **Azure Managed Identity:** Used by Container Apps to pull images from ACR.
- **GitHub Actions + OIDC:** Builds and publishes images and deploys the Container Apps from the `main` branch without storing an Azure client secret in GitHub.

## Monitoring Architecture

Monitoring is environment-specific. The project uses an open-source stack locally and Azure-native monitoring for the cloud deployment.

### Local monitoring — Docker Compose

| Component | Responsibility |
|---|---|
| Prometheus | Scrapes and stores application metrics exposed by FastAPI at `/metrics` |
| Grafana | Visualizes application and service metrics through provisioned dashboards |
| cAdvisor | Collects Docker container resource metrics |

The local monitoring stack is intended to monitor the Docker Compose environment. Windows host-level monitoring with Windows Exporter is not part of the current architecture.

### Azure monitoring — Azure Monitor

| Component | Responsibility |
|---|---|
| Azure Monitor | Observes Azure Container Apps platform and resource metrics |
| Log Analytics Workspace | Centralized storage and querying of diagnostic logs |
| Azure Monitor Alerts | Notifications for selected availability and resource conditions |

Azure Monitor is used for cloud resource monitoring rather than deploying a second Prometheus/Grafana stack in Azure. Log Analytics diagnostic collection and alert rules are follow-up configuration tasks; they must be enabled before historical log queries and alerting are considered operational.

## Technology Stack

- **Language:** Python
- **AI & Orchestration:** LangChain, LangGraph
- **LLM Providers:** Ollama, OpenAI, Azure OpenAI
- **Retrieval:** ChromaDB, BM25, Sentence Transformers
- **API:** FastAPI, Uvicorn
- **Containerization:** Docker, Docker Compose
- **Local Monitoring:** Prometheus, Grafana, cAdvisor
- **Cloud Platform:** Microsoft Azure
- **Cloud Container Services:** Azure Container Apps, Azure Container Registry
- **Cloud Monitoring:** Azure Monitor, Log Analytics
- **CI/CD:** GitHub Actions, Azure OIDC
- **Testing:** pytest

## Features

- Multi-agent orchestration with specialized RAG and application agents.
- REST API with request validation and health checks.
- Structured JSON logging and request ID tracking.
- Prometheus metrics for API performance and request monitoring.
- Local container resource monitoring with cAdvisor.
- Grafana dashboards with automatic provisioning.
- Docker Compose-based local multi-service deployment.
- Cloud deployment to Azure Container Apps.
- Azure Container Registry integration for container image storage and distribution.
- GitHub Actions pipeline for automated tests, Docker builds, and Azure deployment on pushes to `main`.
- OIDC-based GitHub-to-Azure authentication without a stored Azure client secret.
- Versioned ChromaDB snapshots distributed through GitHub Releases rather than committed to the source repository.

### Local Monitoring Dashboard

![Grafana Monitoring Dashboard](assets/screenshots/grafana-dashboard.jpg)

## API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| GET | `/health` | Service health check |
| POST | `/api/v1/ask` | Submit a question |
| GET | `/metrics` | Prometheus metrics |
| GET | `/docs` | Interactive API documentation |

Example request:

```json
{
  "question": "Bankaların çağrı merkezleri için yıllık ulaşılabilirlik seviyesi en az yüzde kaç olmalıdır? Bu oran nasıl hesaplanır?"
}
```

## Getting Started — Local Environment

### Prerequisites

- Docker Desktop and Docker Compose
- Ollama with the configured model, or an OpenAI/Azure OpenAI API key
- ChromaDB snapshot extracted under `data/chroma/`

### Obtain the ChromaDB snapshot

The ChromaDB index is distributed separately as a versioned GitHub Release asset and is not stored in the Git repository.

Download [`data-chroma-v1.zip`](https://github.com/milsever/production-ai-pipeline/releases/download/chroma-v1/data-chroma-v1.zip) and extract it from the repository root. The archive contains the `data/chroma/` directory structure expected by the application and Dockerfile.

### Configuration

Create a local environment file:

```powershell
Copy-Item .env.example .env
```

Configure the LLM provider and required environment variables.

For the default Ollama configuration:

```powershell
ollama pull gpt-oss:20b
```

Create the external Hugging Face cache volume:

```powershell
docker volume create production-ai-hf-cache
```

### Start Services

```powershell
docker compose up --build -d
```

| Service | URL |
|---|---|
| AI Service API | http://localhost:8000 |
| API Documentation | http://localhost:8000/docs |
| Prometheus | http://localhost:9090 |
| Grafana | http://localhost:3000 |
| cAdvisor | http://localhost:8081 |

The CLI interface from the [Agentic AI Workflow](https://github.com/milsever/agentic-ai-workflow) project is also retained.

## Run Tests

Install development dependencies and run the test suite:

```powershell
pip install -r requirements-dev.txt
python -m pytest
```

The test suite uses mocks where appropriate and does not require live LLM inference for the covered workflows.

## CI/CD Pipeline

The GitHub Actions workflow is configured to perform the following steps:

1. Runs the automated test suite.
2. Downloads the pinned ChromaDB snapshot from the `chroma-v1` GitHub Release and extracts it into `data/chroma/`.
3. Builds the Docker image.
4. On pushes to `main`, authenticates to Azure using OIDC, pushes a commit-SHA-tagged image to ACR, and updates both Azure Container Apps.

The GitHub repository uses Actions variables for the Azure client, tenant, and subscription identifiers. No Azure client secret is required for the OIDC flow.

## Project Structure

```text
.
├── src/rag_assistant/       # Agents, API, retrieval and tools
├── tests/                   # Automated tests
├── monitoring/
│   ├── prometheus/          # Prometheus configuration
│   └── grafana/             # Dashboards and provisioning
├── data/
│   ├── documents/           # Local source document directories
│   └── chroma/              # Local vector database (downloaded separately)
├── assets/                  # Project images
├── .github/workflows/       # GitHub Actions CI/CD workflow
├── Dockerfile
├── compose.yaml
├── requirements.txt
└── requirements-dev.txt
```

## Notes

- The customer application API uses mock data for demonstration purposes.
- Source documents and the ChromaDB index are not included in the Git repository. The ChromaDB index is distributed through GitHub Releases.
- The local environment uses Ollama by default; cloud deployment uses the configured OpenAI API provider.
- Azure cloud monitoring is based on Azure Monitor. Log Analytics diagnostic collection and alert rules are documented as follow-up configuration tasks.
