"""
Structured JSON Logging Formatter for Grannus RuralCare AI.

Guarantees:
  - Machine-readable JSON output for CloudWatch / Elasticsearch / Loki
  - Correlation via request_id
  - Automatic scrubbing of Aadhaar, ABHA, mobile numbers, and emails (Zero-PHI)
"""
import json
import logging
import time
from app.security.phi_protection import sanitize_log_message


class JsonLogFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        log_obj = {
            "timestamp": self.formatTime(record, self.datefmt) if self.datefmt else time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(record.created)),
            "level": record.levelname,
            "logger": record.name,
            "message": sanitize_log_message(record.getMessage()),
            "module": record.module,
            "funcName": record.funcName,
            "lineNo": record.lineno,
        }

        # Include request_id if available on the record
        if hasattr(record, "request_id"):
            log_obj["request_id"] = record.request_id

        if record.exc_info:
            log_obj["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_obj)


def configure_structured_logging():
    """Apply structured JSON log formatter to root handler."""
    handler = logging.StreamHandler()
    handler.setFormatter(JsonLogFormatter())
    root_logger = logging.getLogger()
    root_logger.handlers = [handler]
    root_logger.setLevel(logging.INFO)
