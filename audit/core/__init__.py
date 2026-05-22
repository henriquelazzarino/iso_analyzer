"""Core package: logger only — orchestrator imported lazily to avoid cycles."""
from .logger import setup_logger, get_logger  # noqa: F401

# Lazily expose `run` and `AuditOptions` so importing utils/git etc. does not
# pull the whole orchestrator graph (which would create circular imports).
def __getattr__(name):  # pragma: no cover - simple lazy proxy
    if name in ("run", "AuditOptions"):
        from .orchestrator import run, AuditOptions  # local import
        return {"run": run, "AuditOptions": AuditOptions}[name]
    raise AttributeError(name)
