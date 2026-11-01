"""Production WSGI entry point."""

from server import create_app

app = create_app()
