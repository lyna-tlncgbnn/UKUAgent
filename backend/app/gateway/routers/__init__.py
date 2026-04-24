__all__ = [
    "agents",
    "artifacts",
    "assistants_compat",
    "channels",
    "mcp",
    "memory",
    "models",
    "runs",
    "skills",
    "suggestions",
    "thread_runs",
    "threads",
    "uploads",
]


def __getattr__(name: str):
    if name not in __all__:
        raise AttributeError(name)

    import importlib

    return importlib.import_module(f"{__name__}.{name}")
