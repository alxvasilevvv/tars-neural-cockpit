"""Fixtures for MCP client tests.

Lives outside the standard ``tests/`` import path because
``mock_mcp_server.py`` is a runnable Python module that we
spawn as a subprocess from the test suite. Keeping it next
to the tests but in its own package avoids pytest collecting
the script as a test module.
"""
