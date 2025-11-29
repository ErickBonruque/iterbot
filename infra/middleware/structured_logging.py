"""Middleware for structured logging of requests and responses."""
import time
from typing import Callable

import structlog
from django.http import HttpRequest, HttpResponse

logger = structlog.get_logger(__name__)


class StructuredLoggingMiddleware:
    """Middleware that logs all requests and responses in structured JSON format."""

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        start_time = time.time()
        
        # Log request
        logger.info(
            "request_started",
            method=request.method,
            path=request.path,
            user_agent=request.headers.get("User-Agent", ""),
            remote_addr=self._get_client_ip(request),
        )
        
        # Process request
        response = self.get_response(request)
        
        # Calculate duration
        duration_ms = (time.time() - start_time) * 1000
        
        # Log response
        logger.info(
            "request_completed",
            method=request.method,
            path=request.path,
            status_code=response.status_code,
            duration_ms=round(duration_ms, 2),
        )
        
        return response

    def process_exception(
        self, request: HttpRequest, exception: Exception
    ) -> None:
        """Log exceptions with full context."""
        logger.error(
            "request_exception",
            method=request.method,
            path=request.path,
            exception_type=type(exception).__name__,
            exception_message=str(exception),
            exc_info=True,
        )

    @staticmethod
    def _get_client_ip(request: HttpRequest) -> str:
        """Extract client IP from request, considering proxies."""
        x_forwarded_for = request.headers.get("X-Forwarded-For")
        if x_forwarded_for:
            return x_forwarded_for.split(",")[0].strip()
        return request.META.get("REMOTE_ADDR", "")
