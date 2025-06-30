# GOALS

Setup observability for services implemented in the previous lab, including:

- Scrape metrics with Prometheus and query with PromQL  
- Visualize using Dashboard with Grafana  
- Trace with OpenTelemetry & Jaeger  

---

## SYSTEM SETUP

### 1. PROMETHEUS

#### REST-service

- Use the same port of the service because the traffic is low and to reduce complexity. This is possible because both Prometheus and REST use plain HTTP.
- Prometheus works as a middleware in FastAPI webserver.

**Metrics scraped:**
- `http_request_duration_seconds`
- `http_requests_total`

**Tested PromQL queries:**
- Rate in the last 1 minute
- Latency p95 in the last 5 minutes
- Error rate in the last 5 minutes

#### gRPC-service

- Use different port since gRPC uses HTTP/2 while Prometheus uses HTTP.
- Prometheus works as an Interceptor.

**Metrics scraped:**
- `grpc_server_handling_seconds`

**Tested PromQL queries:**
- Latency p95 in the last 5 minutes

---

### 2. GRAFANA

- Custom Dashboard with panels:
  1. REST-service Rate
  2. REST-service Latency p95
  3. REST-service Error Rate
  4. gRPC-service Latency p95

---

### 3. OPENTELEMETRY & JAEGER

- Used protocol: OTLP-gRPC
- Instrument both REST & gRPC-service to have trace from beginning to end

---

### 4. TESTING

- Testscript to CURL request POST then GET method to REST-service every 2 seconds
- GET method is always successful
- POST method
  - Add new Item with random name from a fixed limited pool
  - Naming duplication is not allowed
- Expectation: Error rate of POST method is increased gradually

---

## HOW TO USE
### START UP
`docker compose up -d --build`
### Prometheus
http://localhost:9090
### Grafana
http://localhost:3000
### Jaeger
http://localhost:16686
