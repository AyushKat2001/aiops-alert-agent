import time
import random
from prometheus_client import start_http_server, Counter, Gauge, Histogram

REQUEST_COUNT = Counter(
    'app_requests_total',
    'Total requests',
    ['method', 'endpoint', 'status']
)

REQUEST_LATENCY = Histogram(
    'app_request_latency_seconds',
    'Request latency',
    ['endpoint']
)

MEMORY_USAGE = Gauge(
    'app_memory_usage_bytes',
    'Simulated memory usage in bytes'
)

ERROR_RATE = Gauge(
    'app_error_rate',
    'Simulated error rate percentage'
)

CPU_USAGE = Gauge(
    'app_cpu_usage_percent',
    'Simulated CPU usage percentage'
)

def simulate_metrics():
    while True:
        REQUEST_COUNT.labels(
            method='GET',
            endpoint='/api/users',
            status='200'
        ).inc(random.randint(1, 10))

        REQUEST_COUNT.labels(
            method='GET',
            endpoint='/api/users',
            status='500'
        ).inc(random.randint(0, 2))

        with REQUEST_LATENCY.labels(endpoint='/api/users').time():
            time.sleep(random.uniform(0.01, 0.1))

        MEMORY_USAGE.set(random.uniform(100_000_000, 900_000_000))
        ERROR_RATE.set(random.uniform(0, 15))
        CPU_USAGE.set(random.uniform(10, 95))

        time.sleep(5)

if __name__ == '__main__':
    start_http_server(8000)
    print("Metrics server running on port 8000")
    simulate_metrics()