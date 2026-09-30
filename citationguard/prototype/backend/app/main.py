import os
import logging
import time
from uuid import uuid4

from fastapi import FastAPI, Request
from dotenv import load_dotenv
from fastapi.middleware.cors import CORSMiddleware

load_dotenv()

from app.api import account, audits, citation_bindings, evidence, exports, papers, projects, retrieval, reviews

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO").upper(),
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger("citation_audit.http")

app = FastAPI(
    title="Citation Accuracy Checker Prototype",
    version="0.1.0",
    description="Prototype API for evidence-grounded citation accuracy checking workflows.",
)

cors_origins = [
    origin.strip()
    for origin in os.getenv("CORS_ALLOW_ORIGINS", "http://127.0.0.1:5173,http://localhost:5173").split(",")
    if origin.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def log_requests(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID") or str(uuid4())
    started = time.perf_counter()
    try:
        response = await call_next(request)
    except Exception:
        logger.exception(
            "request_failed request_id=%s method=%s path=%s duration_ms=%.2f",
            request_id,
            request.method,
            request.url.path,
            (time.perf_counter() - started) * 1000,
        )
        raise
    duration_ms = (time.perf_counter() - started) * 1000
    response.headers["X-Request-ID"] = request_id
    logger.info(
        "request_completed request_id=%s method=%s path=%s status=%s duration_ms=%.2f",
        request_id,
        request.method,
        request.url.path,
        response.status_code,
        duration_ms,
    )
    return response

app.include_router(projects.router)
app.include_router(account.router)
app.include_router(papers.router)
app.include_router(evidence.router)
app.include_router(audits.router)
app.include_router(citation_bindings.router)
app.include_router(exports.router)
app.include_router(retrieval.router)
app.include_router(reviews.router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
