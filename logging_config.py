import json
import logging
import logging.handlers
import sys
import os
from datetime import datetime, timezone


LOG_DIR = os.getenv('LOG_DIR', 'logs')
# Rotate at 10 MB, keep 7 backup files
LOG_MAX_BYTES = 10 * 1024 * 1024
LOG_BACKUP_COUNT = 7


def _log_file_path() -> str:
    """Return a dated log file path like logs/app.20260521.log."""
    date_str = datetime.now(timezone.utc).strftime('%Y%m%d')
    return os.path.join(LOG_DIR, f'app.{date_str}.log')


class JsonFormatter(logging.Formatter):
    """Structured JSON formatter — every record includes a UTC timestamp."""

    def format(self, record: logging.LogRecord) -> str:
        payload = {
            'timestamp': datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            'level': record.levelname,
            'logger': record.name,
            'message': record.getMessage(),
        }
        if record.exc_info:
            payload['exception'] = self.formatException(record.exc_info)
        if hasattr(record, 'extra'):
            payload.update(record.extra)
        return json.dumps(payload)


def _make_formatter(is_production: bool) -> logging.Formatter:
    if is_production:
        return JsonFormatter()
    return logging.Formatter(
        fmt='%(asctime)s [%(levelname)s] %(name)s — %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S',
    )


def configure_logging(app) -> None:
    """
    Configure application logging to stdout and a dated rotating log file.

    Log file name: logs/app.YYYYMMDD.log (date computed at startup, UTC).
    Rotates at 10 MB; keeps 7 backups.
    Development: human-readable lines.
    Production: JSON-structured lines for log aggregators.
    """
    env = os.getenv('FLASK_ENV', 'development')
    is_production = env == 'production'

    log_level = logging.INFO if not app.debug else logging.DEBUG
    formatter = _make_formatter(is_production)

    # --- stdout handler ---
    stdout_handler = logging.StreamHandler(sys.stdout)
    stdout_handler.setFormatter(formatter)

    # --- rotating file handler (dated filename) ---
    log_file = _log_file_path()
    os.makedirs(LOG_DIR, exist_ok=True)
    file_handler = logging.handlers.RotatingFileHandler(
        log_file,
        maxBytes=LOG_MAX_BYTES,
        backupCount=LOG_BACKUP_COUNT,
        encoding='utf-8',
    )
    file_handler.setFormatter(formatter)

    root = logging.getLogger()
    root.setLevel(log_level)
    root.handlers = [stdout_handler, file_handler]

    # Suppress noisy third-party loggers
    logging.getLogger('sqlalchemy.engine').setLevel(logging.WARNING)
    if is_production:
        logging.getLogger('werkzeug').setLevel(logging.WARNING)

    app.logger.info(
        'Logging configured | env=%s level=%s log_file=%s',
        env,
        logging.getLevelName(log_level),
        log_file,
    )
