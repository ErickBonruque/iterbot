"""Middleware to add correlation ID to each request."""
import uuid
from typing import Callable

import structlog
from django.http import HttpRequest, HttpResponse

logger = structlog.get_logger(__name__)


class CorrelationIdMiddleware:
    """Middleware that adds a correlation ID to each request for distributed tracing."""

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        # Get or generate correlation ID
        correlation_id = request.headers.get("X-Correlation-ID", str(uuid.uuid4()))
        
        # Store in request for access in views
        request.correlation_id = correlation_id  # type: ignore[attr-defined]
        
        # Add to structlog context
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(
            correlation_id=correlation_id,
            request_method=request.method,
            request_path=request.path,
        )
        
        # Process request
        response = self.get_response(request)
        
        # Add correlation ID to response headers
        response["X-Correlation-ID"] = correlation_id
        
        return response
