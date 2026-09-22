#!/usr/bin/env python3
"""Локальный development server. В production используйте gunicorn + wsgi.py."""

from app import create_app
from settings import config

app = create_app()

if __name__ == "__main__":
    app.run(
        debug=not config.IS_PRODUCTION,
        host="127.0.0.1",
        port=8080,
    )
