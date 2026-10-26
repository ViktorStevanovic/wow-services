"""ASGI entry point for servers (`fastapi dev`, uvicorn). Tests use `create_app()` instead."""

from app.main import create_app

app = create_app()
