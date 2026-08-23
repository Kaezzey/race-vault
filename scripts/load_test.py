"""Bounded concurrent load and SLO check for RaceVault HTTP endpoints."""

from __future__ import annotations

import argparse
import json
import math
import statistics
import threading
import time
import urllib.error
import urllib.request
from dataclasses import dataclass


@dataclass(frozen=True)
class Observation:
    status: int
    elapsed_seconds: float


def _percentile(values: list[float], probability: float) -> float:
    ordered = sorted(values)
    if not ordered:
        return math.inf
    index = math.ceil(probability * len(ordered)) - 1
    return ordered[max(0, min(index, len(ordered) - 1))]


def _request(url: str, payload: bytes, timeout: float) -> Observation:
    started = time.perf_counter()
    request = urllib.request.Request(
        url,
        data=payload,
        method="POST",
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            status = response.status
            response.read()
    except urllib.error.HTTPError as error:
        status = error.code
        error.read()
    except (OSError, TimeoutError):
        status = 0
    return Observation(status=status, elapsed_seconds=time.perf_counter() - started)


def run_load(
    *,
    url: str,
    query: str,
    duration_seconds: float,
    concurrency: int,
    timeout_seconds: float,
) -> list[Observation]:
    payload = json.dumps({"query": query}).encode()
    deadline = time.monotonic() + duration_seconds
    observations: list[Observation] = []
    lock = threading.Lock()

    def worker() -> None:
        local = []
        while time.monotonic() < deadline:
            local.append(_request(url, payload, timeout_seconds))
        with lock:
            observations.extend(local)

    threads = [threading.Thread(target=worker) for _ in range(concurrency)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    return observations


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--url", default="http://localhost:8000/v1/retrieval/search"
    )
    parser.add_argument("--query", default="What is the caliper bridge bolt torque?")
    parser.add_argument("--duration-seconds", type=float, default=1800)
    parser.add_argument("--concurrency", type=int, default=4)
    parser.add_argument("--timeout-seconds", type=float, default=60)
    parser.add_argument("--p95-slo-seconds", type=float, default=1.5)
    parser.add_argument("--maximum-error-rate", type=float, default=0.01)
    args = parser.parse_args(argv)
    observations = run_load(
        url=args.url,
        query=args.query,
        duration_seconds=args.duration_seconds,
        concurrency=args.concurrency,
        timeout_seconds=args.timeout_seconds,
    )
    successful = [item.elapsed_seconds for item in observations if item.status == 200]
    expected_rejections = sum(item.status == 429 for item in observations)
    unexpected = sum(item.status not in {200, 429} for item in observations)
    error_rate = unexpected / len(observations) if observations else 1.0
    p95 = _percentile(successful, 0.95)
    median = statistics.median(successful) if successful else math.inf
    print(f"requests={len(observations)} success={len(successful)}")
    print(f"expected_429={expected_rejections} unexpected={unexpected}")
    print(f"latency_seconds p50={median:.3f} p95={p95:.3f}")
    print(f"unexpected_error_rate={error_rate:.4f}")
    return 0 if p95 <= args.p95_slo_seconds and error_rate < args.maximum_error_rate else 1


if __name__ == "__main__":
    raise SystemExit(main())
