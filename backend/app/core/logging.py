import logging

import structlog
from structlog.typing import Processor

from app.core.config import Environment, Settings


class _AppLogHandler(logging.StreamHandler):  # type: ignore[type-arg]  # stdlib generic over stream
    """Marker type, so reconfiguring replaces our handler without touching others (e.g. pytest)."""


def configure_logging(settings: Settings) -> None:
    """Route structlog and stdlib logging (uvicorn, sqlalchemy...) through one renderer.

    JSON lines in production, coloured console output otherwise.
    """
    shared: list[Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
    ]
    renderer: Processor
    if settings.environment is Environment.PRODUCTION:
        shared.append(structlog.processors.dict_tracebacks)
        renderer = structlog.processors.JSONRenderer()
    else:
        renderer = structlog.dev.ConsoleRenderer()

    structlog.configure(
        processors=[*shared, structlog.stdlib.ProcessorFormatter.wrap_for_formatter],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    handler = _AppLogHandler()
    handler.setFormatter(
        structlog.stdlib.ProcessorFormatter(
            foreign_pre_chain=shared,
            processors=[structlog.stdlib.ProcessorFormatter.remove_processors_meta, renderer],
        )
    )
    root = logging.getLogger()
    root.handlers = [h for h in root.handlers if not isinstance(h, _AppLogHandler)]
    root.addHandler(handler)
    root.setLevel(settings.log_level.upper())

    for name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        uvicorn_logger = logging.getLogger(name)
        uvicorn_logger.handlers.clear()
        uvicorn_logger.propagate = True
    # RequestContextMiddleware logs every request with its request ID instead.
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
