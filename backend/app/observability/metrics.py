"""
Prometheus Metrics and Telemetry Collector for Grannus RuralCare AI.

Tracks:
  - Triage level distributions (HIGH, MEDIUM, LOW, PENDING_REVIEW)
  - Processing latencies across pipeline stages
  - STT confidence distribution and fallback rates
  - Error rates and circuit breaker events
"""
import time
from typing import Dict
from collections import defaultdict


class MetricsCollector:
    def __init__(self):
        self.requests_total: Dict[str, int] = defaultdict(int)  # endpoint -> count
        self.triage_total: Dict[str, int] = defaultdict(int)    # level -> count
        self.errors_total: Dict[str, int] = defaultdict(int)    # error_type -> count
        self.latencies: Dict[str, list] = defaultdict(list)     # stage -> list of durations
        self.start_time = time.time()

    def record_request(self, endpoint: str):
        self.requests_total[endpoint] += 1

    def record_triage(self, level: str):
        self.triage_total[level.upper()] += 1

    def record_error(self, error_type: str):
        self.errors_total[error_type] += 1

    def record_latency(self, stage: str, duration_sec: float):
        # Keep last 1000 measurements
        if len(self.latencies[stage]) > 1000:
            self.latencies[stage].pop(0)
        self.latencies[stage].append(duration_sec)

    def generate_prometheus_output(self) -> str:
        """Render metrics in standard Prometheus exposition format."""
        lines = []
        lines.append("# HELP grannus_uptime_seconds Total uptime of the Grannus service.")
        lines.append("# TYPE grannus_uptime_seconds gauge")
        lines.append(f"grannus_uptime_seconds {time.time() - self.start_time:.1f}")

        lines.append("# HELP grannus_requests_total Total number of HTTP requests.")
        lines.append("# TYPE grannus_requests_total counter")
        for ep, count in self.requests_total.items():
            lines.append(f'grannus_requests_total{{endpoint="{ep}"}} {count}')

        lines.append("# HELP grannus_triage_cases_total Total triage cases categorized by priority level.")
        lines.append("# TYPE grannus_triage_cases_total counter")
        for level in ["HIGH", "MEDIUM", "LOW", "PENDING_REVIEW"]:
            count = self.triage_total.get(level, 0)
            lines.append(f'grannus_triage_cases_total{{level="{level}"}} {count}')

        lines.append("# HELP grannus_errors_total Total system and pipeline errors.")
        lines.append("# TYPE grannus_errors_total counter")
        for err, count in self.errors_total.items():
            lines.append(f'grannus_errors_total{{type="{err}"}} {count}')

        lines.append("# HELP grannus_avg_latency_seconds Average latency by pipeline stage.")
        lines.append("# TYPE grannus_avg_latency_seconds gauge")
        for stage, durations in self.latencies.items():
            avg = sum(durations) / len(durations) if durations else 0.0
            lines.append(f'grannus_avg_latency_seconds{{stage="{stage}"}} {avg:.4f}')

        return "\n".join(lines) + "\n"


_metrics = MetricsCollector()


def get_metrics() -> MetricsCollector:
    return _metrics
