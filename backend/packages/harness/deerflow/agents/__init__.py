"""DeerFlow agent exports with lazy loading."""

from __future__ import annotations

from importlib import import_module
from deerflow.agents.lead_agent import make_lead_agent

_EXPORTS = {
    "get_checkpointer": "deerflow.agents.checkpointer",
    "make_checkpointer": "deerflow.agents.checkpointer",
    "reset_checkpointer": "deerflow.agents.checkpointer",
    "create_deerflow_agent": "deerflow.agents.factory",
    "Next": "deerflow.agents.features",
    "Prev": "deerflow.agents.features",
    "RuntimeFeatures": "deerflow.agents.features",
    "SandboxState": "deerflow.agents.thread_state",
    "ThreadState": "deerflow.agents.thread_state",
}

__all__ = ["make_lead_agent", *_EXPORTS]
def __getattr__(name: str):
    module_name = _EXPORTS.get(name)
    if module_name is None:
        raise AttributeError(name)

    module = import_module(module_name)
    return getattr(module, name)
