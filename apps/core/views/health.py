"""Health check endpoint for monitoring."""
from typing import Any, Dict

import structlog
from django.core.cache import cache
from django.db import connection
from django.http import JsonResponse
from django.views import View

logger = structlog.get_logger(__name__)


class HealthCheckView(View):
    """Health check endpoint that verifies database and cache connectivity."""

    def get(self, request: Any) -> JsonResponse:
        """
        Check the health of the application.
        
        Returns:
            JsonResponse with status and component health information.
        """
        health_status = {
            "status": "healthy",
            "components": {},
        }
        
        # Check database
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
            health_status["components"]["database"] = "healthy"
        except Exception as e:
            logger.error("database_health_check_failed", error=str(e))
            health_status["components"]["database"] = "unhealthy"
            health_status["status"] = "unhealthy"
        
        # Check cache (Redis)
        try:
            cache.set("health_check", "ok", timeout=10)
            if cache.get("health_check") == "ok":
                health_status["components"]["cache"] = "healthy"
            else:
                raise Exception("Cache read/write test failed")
        except Exception as e:
            logger.error("cache_health_check_failed", error=str(e))
            health_status["components"]["cache"] = "unhealthy"
            health_status["status"] = "unhealthy"
        
        status_code = 200 if health_status["status"] == "healthy" else 503
        return JsonResponse(health_status, status=status_code)
