import os
import logging
import json
import time
import uuid
from datetime import datetime, timezone

from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import Response
from prometheus_client import (
    Counter,
    Gauge,
    Histogram,
    generate_latest,
    CONTENT_TYPE_LATEST,
)

from rag_assistant.multi_agent_graph import build_multi_agent_graph
from rag_assistant.schemas import (
    AskRequest,
    AskResponse,
    HealthResponse,
)

os.environ["HF_HUB_DISABLE_PROGRESS_BARS"] = "1"

class JsonFormatter(logging.Formatter):
    def format(self, record):
        log_data = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        # HTTP request information
        for field in (
                "request_id",
                "method",
                "path",
                "status_code",
                "duration_ms",
        ):
            value = getattr(record, field, None)
            if value is not None:
                log_data[field] = value

        if record.exc_info:
            log_data["exception"] = self.formatException(
                record.exc_info
            )

        return json.dumps(log_data, ensure_ascii=False)

handler = logging.StreamHandler()
handler.setFormatter(JsonFormatter())

root_logger = logging.getLogger()
root_logger.setLevel(logging.INFO)
root_logger.handlers.clear()
root_logger.addHandler(handler)

logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpx2").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
logging.getLogger("sentence_transformers").setLevel(logging.WARNING)
logging.getLogger("transformers").setLevel(logging.ERROR)

logger = logging.getLogger(__name__)

HTTP_REQUESTS = Counter(
    "http_requests_total",
    "Total number of HTTP requests.",
    ["method", "path", "status_code"],
)

HTTP_REQUEST_DURATION = Histogram(
    "http_request_duration_seconds",
    "HTTP request duration in seconds.",
    ["method", "path"],
)

HTTP_REQUESTS_IN_PROGRESS = Gauge(
    "http_requests_in_progress",
    "Number of HTTP requests currently being processed.",
)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Initialize the multi-agent workflow once
    when the API application starts.
    """
    logger.info("Initializing multi-agent workflow...")

    app.state.graph = build_multi_agent_graph()

    logger.info("Multi-agent workflow initialized.")
    yield
    logger.info("Shutting down API application.")

app = FastAPI(
    title="Production AI Service",
    description=(
        "REST API for an enterprise multi-agent "
        "knowledge assistant."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

@app.middleware("http")
async def request_logging_middleware(request: Request, call_next):
    # Prevent Prometheus scraping from generating its own metrics.
    if request.url.path == "/metrics":
        return await call_next(request)

    request_id = str(uuid.uuid4())
    start_time = time.perf_counter()

    status_code = 500

    HTTP_REQUESTS_IN_PROGRESS.inc()

    try:
        response = await call_next(request)

        status_code = response.status_code
        response.headers["X-Request-ID"] = request_id

        return response

    except Exception:
        logger.exception(
            "HTTP request failed",
            extra={
                "request_id": request_id,
                "method": request.method,
                "path": request.url.path,
                "status_code": status_code,
            },
        )
        raise

    finally:
        duration_seconds = time.perf_counter() - start_time
        duration_ms = round(duration_seconds * 1000, 2)

        route = request.scope.get("route")
        path = getattr(route, "path", request.url.path)

        HTTP_REQUESTS.labels(
            method=request.method,
            path=path,
            status_code=str(status_code),
        ).inc()

        HTTP_REQUEST_DURATION.labels(
            method=request.method,
            path=path,
        ).observe(duration_seconds)

        HTTP_REQUESTS_IN_PROGRESS.dec()

        logger.info(
            "HTTP request finished",
            extra={
                "request_id": request_id,
                "method": request.method,
                "path": path,
                "status_code": status_code,
                "duration_ms": duration_ms,
            },
        )

@app.get("/health", response_model=HealthResponse, tags=["Health"], )
def health_check():
    return HealthResponse(status="ok")

@app.get("/metrics", include_in_schema=False)
def metrics():
    return Response(
        content=generate_latest(),
        headers={"Content-Type": CONTENT_TYPE_LATEST},
    )

@app.post("/api/v1/ask", response_model=AskResponse, tags=["Assistant"], )
def ask_question(
        payload: AskRequest,
        request: Request,
):
    graph = request.app.state.graph

    try:
        result = graph.invoke({
            "messages": [("user", payload.question)]
        })

        routes = result.get("routes", [])
        messages = result.get("messages", [])

        if not messages:
            raise RuntimeError(
                "The workflow returned no messages."
            )

        answer = messages[-1].content

        if isinstance(answer, list):
            answer = "\n".join(
                str(block.get("text", block)) if isinstance(block, dict) else str(block) for block in answer
            )

        specialist_names = {
            "rag_agent": "RAG Specialist",
            "application_agent": "Application Specialist",
        }

        selected_specialists = [
            specialist_names.get(route, route)
            for route in routes
        ]

        return AskResponse(
            answer=str(answer),
            routes=routes,
            selected_specialists=selected_specialists,
        )

    except Exception:
        logger.exception(
            "Multi-agent workflow failed."
        )

        raise HTTPException(
            status_code=500,
            detail="An error occurred while processing the request.",
        )
