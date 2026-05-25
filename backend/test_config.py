"""Test deployment-friendly settings parsing."""

import os
from contextlib import contextmanager

from app.config import Settings


def run():
    expected = ["https://frontend.example.com"]

    with _env("FRONTEND_ORIGINS", '["https://frontend.example.com"]'):
        assert Settings(_env_file=None).frontend_origins == expected
        print("  json origins    -> parsed")

    with _env(
        "FRONTEND_ORIGINS",
        "https://frontend.example.com, https://admin.example.com",
    ):
        assert Settings(_env_file=None).frontend_origins == [
            "https://frontend.example.com",
            "https://admin.example.com",
        ]
        print("  csv origins     -> parsed")

    with _env("FRONTEND_ORIGINS", "https://frontend.example.com"):
        assert Settings(_env_file=None).frontend_origins == expected
        print("  single origin   -> parsed")


@contextmanager
def _env(name: str, value: str):
    previous = os.environ.get(name)
    os.environ[name] = value
    try:
        yield
    finally:
        if previous is None:
            os.environ.pop(name, None)
        else:
            os.environ[name] = previous


run()
print("\nALL CONFIG CHECKS PASSED")
