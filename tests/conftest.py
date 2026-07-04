"""Shared pytest fixtures and configuration for the test suite.

The application modules build a Gemini client at import time, which requires an
API key to be present.  Tests never make real network calls (the client is
mocked), but a placeholder key must exist so the modules can be imported.  We
set one here before any test module imports the application code.
"""

import os

os.environ.setdefault("GEMINI_KEY", "test-key-not-used")
