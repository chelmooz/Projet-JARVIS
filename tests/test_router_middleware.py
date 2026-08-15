#!/usr/bin/env python3
"""Test that there's only one token middleware registered."""

from controllers.router import create_app


class TestSingleTokenMiddleware:
    """RED: Test that only one token middleware is registered."""

    def test_single_token_middleware_registered(self) -> None:
        """RED: Vérifier qu'il n'y a exactement 1 middleware "http" avec "verify_token"."""
        app = create_app()

        # Compter les middlewares http. Middleware (Starlette) n'a pas d'attribut
        # 'name' : le dispatch d'un @app.middleware("http") est exposé via
        # middleware.kwargs["dispatch"], pas comme attribut direct.
        middleware_count = 0
        for middleware in app.user_middleware:
            dispatch = middleware.kwargs.get("dispatch")
            if dispatch is not None and getattr(dispatch, "__name__", None) == "verify_token_middleware":
                middleware_count += 1

        assert middleware_count == 1, f"Expected 1 verify_token_middleware, got {middleware_count}"
