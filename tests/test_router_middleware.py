#!/usr/bin/env python3
"""Test that there's only one token middleware registered."""
import pytest
from fastapi import FastAPI, Request
from fastapi.responses import Response
from starlette.testclient import TestClient

from controllers.router import create_app


class TestSingleTokenMiddleware:
    """RED: Test that only one token middleware is registered."""

    def test_single_token_middleware_registered(self) -> None:
        """RED: Vérifier qu'il n'y a exactement 1 middleware "http" avec "verify_token"."""
        app = create_app()
        
        # Compter les middlewares http
        middleware_count = 0
        for middleware in app.user_middleware:
            if hasattr(middleware, "name") and middleware.name == "verify_token_middleware":
                middleware_count += 1
        
        assert middleware_count == 1, (
            f"Expected 1 verify_token_middleware, got {middleware_count}"
        )