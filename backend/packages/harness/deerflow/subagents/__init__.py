"""Subagent exports with lazy loading."""

from __future__ import annotations

from importlib import import_module

_EXPORTS = {
    "SubagentConfig": "deerflow.subagents.config",
    "SubagentExecutor": "deerflow.subagents.executor",
    "SubagentResult": "deerflow.subagents.executor",
    "get_available_subagent_names": "deerflow.subagents.registry",
    "get_subagent_config": "deerflow.subagents.registry",
    "list_subagents": "deerflow.subagents.registry",
}

__all__ = list(_EXPORTS)


def __getattr__(name: str):
    module_name = _EXPORTS.get(name)
    if module_name is None:
        raise AttributeError(name)

    module = import_module(module_name)
    return getattr(module, name)
