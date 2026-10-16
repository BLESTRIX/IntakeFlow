import json
import logging
import time
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError
from starlette.exceptions import HTTPException

from app.api.routes import router
from app.core.errors import DomainError

app = FastAPI(
    title="IntakeFlow",
    version="0.1.0",
    description="Organization-scoped maintenance intake. Cookie authentication + X-CSRF-Token for mutations. Tenant ownership and staff roles are enforced by services; durable commands reference reviewed and source versions.",
)
app.include_router(router)
logger = logging.getLogger("intakeflow")
logging.basicConfig(level=logging.INFO, format="%(message)s")


@app.middleware("http")
async def request_context(request: Request, call_next):
    request.state.request_id = str(uuid4())
    start = time.perf_counter()
    response = await call_next(request)
    response.headers["X-Request-ID"] = request.state.request_id
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Cache-Control"] = "no-store"
    logger.info(
        json.dumps(
            {
                "event": "http",
                "request_id": request.state.request_id,
                "method": request.method,
                "route": request.scope.get("route").path
                if request.scope.get("route")
                else "unknown",
                "status": response.status_code,
                "latency_ms": round((time.perf_counter() - start) * 1000, 1),
            }
        )
    )
    return response


def error(request, code, message, status, **extra):
    return JSONResponse(
        status_code=status,
        content={
            "code": code,
            "message": message,
            "request_id": getattr(request.state, "request_id", "unknown"),
            **extra,
        },
    )


@app.exception_handler(DomainError)
async def domain_error(request, exc):
    return error(request, exc.code, exc.message, exc.status)


@app.exception_handler(RequestValidationError)
async def validation_error(request, exc):
    fields = [{"field": ".".join(map(str, e["loc"])), "message": e["msg"]} for e in exc.errors()]
    return error(request, "VALIDATION_ERROR", "Check the submitted fields", 422, fields=fields)


@app.exception_handler(IntegrityError)
async def integrity_error(request, exc):
    return error(request, "CONFLICT", "A record already exists or a relationship is invalid", 409)


@app.exception_handler(HTTPException)
async def http_error(request, exc):
    return error(request, "HTTP_ERROR", str(exc.detail), exc.status_code)


@app.exception_handler(Exception)
async def unexpected_error(request, exc):
    logger.error(
        json.dumps(
            {
                "event": "unhandled_error",
                "request_id": getattr(request.state, "request_id", "unknown"),
                "category": type(exc).__name__,
            }
        )
    )
    return error(request, "SERVICE_ERROR", "Service unavailable; retry or contact staff", 503)
