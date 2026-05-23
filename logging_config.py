import json
import logging
import logging.handlers
import os
import socket
import sys
from datetime import datetime, timezone


LOG_DIR = os.getenv('LOG_DIR', 'logs')
# Rotate at 10 MB, keep 7 backup files
LOG_MAX_BYTES = 10 * 1024 * 1024
LOG_BACKUP_COUNT = 7

# Service metadata stamped into every JSON record for OpenSearch indexing.
_SERVICE_NAME = os.getenv('SERVICE_NAME', 'flask-app')
_ENVIRONMENT = os.getenv('FLASK_ENV', 'development')
_HOST = socket.gethostname()


def _log_file_path() -> str:
    """Return a dated log file path like logs/app.20260522.log."""
    date_str = datetime.now(timezone.utc).strftime('%Y%m%d')
    return os.path.join(LOG_DIR, f'app.{date_str}.log')


class JsonFormatter(logging.Formatter):
    """
    Structured JSON formatter.

    Every record includes:
      timestamp  – ISO 8601 UTC string derived from the record's creation time
      level      – log level name
      logger     – logger name (maps to module)
      message    – formatted log message
      service    – value of SERVICE_NAME env var (default: flask-app)
      environment– value of FLASK_ENV env var
      host       – hostname of the machine/container

    Exceptions are serialised into an 'exception' key so they remain
    queryable in OpenSearch rather than being embedded in the message string.
    """

    def format(self, record: logging.LogRecord) -> str:
        payload = {
            'timestamp': datetime.fromtimestamp(record.created, tz=timezone.utc).strftime('%Y-%m-%dT%H:%M:%S.%f')[:-3] + 'Z',
            'level': record.levelname,
            'logger': record.name,
            'message': record.getMessage(),
            'service': _SERVICE_NAME,
            'environment': _ENVIRONMENT,
            'host': _HOST,
        }
        if record.exc_info:
            payload['exception'] = self.formatException(record.exc_info)
        if hasattr(record, 'extra'):
            payload.update(record.extra)
        return json.dumps(payload)


def _use_json() -> bool:
    """
    Return True when JSON output should be used.

    Forced on when LOG_FORMAT=json, or when FLASK_ENV=production.
    This allows development environments to opt in to JSON so that
    Fluent Bit can parse logs locally with the same config as production.
    """
    log_format = os.getenv('LOG_FORMAT', '').lower()
    if log_format == 'json':
        return True
    return _ENVIRONMENT == 'production'


def _make_formatter() -> logging.Formatter:
    if _use_json():
        return JsonFormatter()
    return logging.Formatter(
        fmt='%(asctime)s [%(levelname)s] %(name)s — %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S',
    )


def configure_logging(app) -> None:
    """
    Configure application logging to stdout and a dated rotating log file.

    Log file: logs/app.YYYYMMDD.log  (date computed at startup, UTC).
    Rotates at 10 MB; keeps 7 backups.

    Set LOG_FORMAT=json to force JSON output in any environment.
    JSON output is always used in production and is required for
    Fluent Bit to parse logs without a custom regex parser.
    """
    is_json = _use_json()
    log_level = logging.INFO if not app.debug else logging.DEBUG
    formatter = _make_formatter()

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
    if _ENVIRONMENT == 'production':
        logging.getLogger('werkzeug').setLevel(logging.WARNING)

    app.logger.info(
        'Logging configured | env=%s level=%s format=%s log_file=%s service=%s host=%s',
        _ENVIRONMENT,
        logging.getLevelName(log_level),
        'json' if is_json else 'text',
        log_file,
        _SERVICE_NAME,
        _HOST,
    )
