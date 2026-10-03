"""
Unit and Integration Tests for Phase 4: Infrastructure, Observability, and Operations.

Covers:
  - Liveness endpoint (/health)
  - Readiness endpoint (/ready) with dependency checks
  - Prometheus metrics exposition (/metrics)
  - X-Request-ID propagation and latency tracking middleware
  - Structured JSON logging with zero-PHI sanitization
  - Metrics collector updates (triage distribution, errors, latencies)
"""
import json
import logging
from unittest.mock import patch
from fastapi.testclient import TestClient

from app.main import app
from app.observability.metrics import get_metrics, MetricsCollector
from app.observability.logging_config import JsonLogFormatter

client = TestClient(app)


def test_health_liveness_endpoint():
    res = client.get("/health")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "ok"
    assert "sarvam_key_configured" in data
    assert "gemini_key_configured" in data
    assert "ml_model_loaded" in data


def test_ready_readiness_endpoint():
    res = client.get("/ready")
    assert res.status_code in [200, 503]
    data = res.json()
    assert "status" in data
    assert "sarvam_configured" in data
    assert "gemini_configured" in data


def test_prometheus_metrics_endpoint():
    # Make a request to generate traffic
    client.get("/health")
    res = client.get("/metrics")
    assert res.status_code == 200
    text = res.text
    assert "grannus_uptime_seconds" in text
    assert "grannus_requests_total" in text
    assert "grannus_triage_cases_total" in text


def test_x_request_id_middleware():
    # Request without explicit X-Request-ID generates one
    res1 = client.get("/health")
    assert "x-request-id" in res1.headers
    req_id = res1.headers["x-request-id"]
    assert len(req_id) > 10

    # Request with custom X-Request-ID propagates it
    custom_id = "custom-audit-correlation-uuid-999"
    res2 = client.get("/health", headers={"X-Request-ID": custom_id})
    assert res2.headers.get("x-request-id") == custom_id


def test_metrics_collector_triage_and_errors():
    metrics = get_metrics()
    metrics.record_triage("HIGH")
    metrics.record_triage("MEDIUM")
    metrics.record_triage("LOW")
    metrics.record_error("MockTimeoutError")
    metrics.record_latency("/test/endpoint", 0.045)

    output = metrics.generate_prometheus_output()
    assert 'grannus_triage_cases_total{level="HIGH"}' in output
    assert 'grannus_triage_cases_total{level="MEDIUM"}' in output
    assert 'grannus_triage_cases_total{level="LOW"}' in output
    assert 'grannus_errors_total{type="MockTimeoutError"}' in output
    assert 'grannus_avg_latency_seconds{stage="/test/endpoint"}' in output


def test_structured_json_log_formatter():
    formatter = JsonLogFormatter()
    record = logging.LogRecord(
        name="grannus.test",
        level=logging.INFO,
        pathname="test.py",
        lineno=42,
        msg="Consultation for patient phone 9876543210 and Aadhaar 2345 6789 0123",
        args=(),
        exc_info=None,
    )
    formatted = formatter.format(record)
    log_data = json.loads(formatted)

    assert log_data["level"] == "INFO"
    assert log_data["logger"] == "grannus.test"
    # PHI must be sanitized in JSON logs
    assert "9876543210" not in log_data["message"]
    assert "2345 6789 0123" not in log_data["message"]
    assert "[PHONE_" in log_data["message"]
    assert "[AADHAAR_" in log_data["message"]
