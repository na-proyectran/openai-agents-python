from __future__ import annotations

from examples.realtime.app.agent import get_starting_agent as _app_get_starting_agent

"""Proxy module re-exporting the demo agents.

This keeps the Unity sample using the same agent structure as the
realtime web demo. Modify ``get_starting_agent`` to swap in your own
agents.
"""


def get_starting_agent():
    return _app_get_starting_agent()
