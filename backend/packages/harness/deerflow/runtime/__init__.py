"""LangGraph-compatible runtime exports with lazy loading."""

from __future__ import annotations

from importlib import import_module

_EXPORTS = {
    "ConflictError": "deerflow.runtime.runs",
    "DisconnectMode": "deerflow.runtime.runs",
    "RunManager": "deerflow.runtime.runs",
    "RunRecord": "deerflow.runtime.runs",
    "RunStatus": "deerflow.runtime.runs",
    "UnsupportedStrategyError": "deerflow.runtime.runs",
    "run_agent": "deerflow.runtime.runs",
    "serialize": "deerflow.runtime.serialization",
    "serialize_channel_values": "deerflow.runtime.serialization",
    "serialize_lc_object": "deerflow.runtime.serialization",
    "serialize_messages_tuple": "deerflow.runtime.serialization",
    "get_store": "deerflow.runtime.store",
    "make_store": "deerflow.runtime.store",
    "reset_store": "deerflow.runtime.store",
    "store_context": "deerflow.runtime.store",
    "END_SENTINEL": "deerflow.runtime.stream_bridge",
    "HEARTBEAT_SENTINEL": "deerflow.runtime.stream_bridge",
    "MemoryStreamBridge": "deerflow.runtime.stream_bridge",
    "StreamBridge": "deerflow.runtime.stream_bridge",
    "StreamEvent": "deerflow.runtime.stream_bridge",
    "make_stream_bridge": "deerflow.runtime.stream_bridge",
}

__all__ = list(_EXPORTS)


def __getattr__(name: str):
    module_name = _EXPORTS.get(name)
    if module_name is None:
        raise AttributeError(name)

    module = import_module(module_name)
    return getattr(module, name)
