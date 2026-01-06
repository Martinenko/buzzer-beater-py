"""
WSGI entry point for PythonAnywhere deployment.
FastAPI is ASGI, so we use a2wsgi adapter.
"""
from a2wsgi import ASGIMiddleware
from app.main import app

# Wrap ASGI app in WSGI adapter
application = ASGIMiddleware(app)