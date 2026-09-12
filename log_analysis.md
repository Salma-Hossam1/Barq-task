# Historical Log Analysis

## 1. Scope and Method

The supplied historical logs were analyzed without modifying the original files.

The analysis covered:

* `access.log` — NGINX client-facing request records
* `error.log` — NGINX diagnostic messages
* `application.log` — application request and dependency events

The logs use UTC timestamps.

The analysis used Bash, `grep`, `wc`, and Python for parsing, deduplication, counting, timestamp extraction, latency analysis, and cross-log correlation.

A log record was not automatically treated as a unique client request. Exact duplicate records were removed where appropriate, and `request_id` was used to correlate records across logs.

Malformed records were excluded from structured JSON calculations and were not modified in the original files.

---

# 2. Log Integrity and Structure

## access.log

Results:

```text
Physical lines:             726
Valid JSON records:         725
Malformed JSON records:       1
Distinct request IDs:       720
Duplicate extra records:      5
```

The malformed record was incomplete:

```text
{"timestamp":"2026-08-20T11:12:48Z","request_id":
```

The five duplicate extra records were excluded from request-level calculations.

Therefore:

```text
726 physical lines
- 1 malformed record
= 725 valid records

725 valid records
- 5 duplicate extra records
= 720 distinct client requests
```

## application.log

Results:

```text
Physical lines:             730
Valid JSON records:         729
Malformed JSON records:       1
Duplicate extra records:      2
Distinct application request IDs: 680
```

The malformed record was incomplete:

```text
{"timestamp": "2026-08-20T11:17:00Z","event":
```

The application log contains both HTTP request events and dependency error events, so its total number of unique request IDs is not expected to equal the number of unique client requests in `access.log`.

## error.log

`error.log` is NGINX text output rather than JSON, so JSON parsing is not applicable.

Results:

```text
Total lines:                 68
Request diagnostic lines:    67
NGINX notice:                 1
Malformed records:            0
Exact duplicates:             0
```

The final notice at 11:30 UTC indicates log stream/collector rotation.

---

# 3. Request Volume and HTTP Status Distribution

After removing exact duplicate access records, there were:

```text
720 distinct client requests
```

Status distribution:

```text
200: 615
404:  10
502:  40
503:  47
504:   8
------------
Total: 720
```

Total 5xx responses:

```text
40 + 47 + 8 = 95
```

5xx error rate:

```text
95 / 720 × 100 = 13.19%
```

The 404 responses were not included in the 5xx error rate because HTTP 404 is a 4xx client error rather than a server-side 5xx response.

The denominator for the error rate is the number of distinct client requests, not the number of physical log lines or NGINX upstream attempts.

---

# 4. 502 Analysis — Upstream Connection Failures

There were:

```text
40 final HTTP 502 responses
```

Time window:

```text
First: 2026-08-20T11:05:02.503Z
Last:  2026-08-20T11:09:57.503Z
```

All 40 final 502 responses targeted:

```text
172.23.0.12:8080
```

Path distribution:

```text
/health:   10
/records:  10
/counter:  10
/:         10
```

The NGINX error log contains:

```text
59 connection-refused diagnostics
```

with messages containing:

```text
connect() failed (111: Connection refused)
```

The 59 connection-refused events are greater than the 40 final 502 responses because 19 client requests experienced an initial failed upstream attempt and then succeeded after NGINX retried another upstream.

Therefore:

```text
40 final 502 requests
+ 19 initial failed attempts that later succeeded
= 59 connection-refused events
```

The logs prove that the upstream connection was refused.

They do **not** prove the underlying reason why the upstream refused the connection.

---

# 5. Retry Analysis

There were:

```text
19 requests with upstream retries
```

The retry pattern was:

```text
upstream_status = "502, 200"
```

All 19 eventually succeeded:

```text
Retried requests:              19
Succeeded after retry:         19
Final status of retried requests:
200:                            19
```

Therefore, these retries must not be counted as additional client requests.

A single client request can contain multiple upstream attempts.

---

# 6. 503 Analysis — Application Dependency Failures

There were:

```text
47 application HTTP 503 records
```

Distribution by application instance:

```text
app-02: 24
app-01: 23
```

Distribution by path:

```text
/ready:    23
/counter:  16
/records:   8
```

The application log also contains:

```text
47 dependency_error events
```

Dependency distribution:

```text
Redis:       31
PostgreSQL:  16
```

Time windows:

```text
Redis:
  31 errors
  2026-08-20T11:12:09.524Z
  ->
  2026-08-20T11:15:52.024Z

PostgreSQL:
  16 errors
  2026-08-20T11:20:07.540Z
  ->
  2026-08-20T11:21:45.040Z
```

The 47 application 503 records correspond to the 47 dependency error events.

This indicates that the 503 responses were generated at the application layer as a consequence of dependency failures.

The logs do not establish the underlying cause of the Redis or PostgreSQL failures. They only prove that the application experienced dependency errors.

---

# 7. 504 Analysis — Upstream Response Timeout

There were:

```text
8 HTTP 504 responses
```

Time window:

```text
First: 2026-08-20T11:25:14.501Z
Last:  2026-08-20T11:26:47.001Z
```

All eight requests were:

```text
GET /records
```

Upstream distribution:

```text
172.23.0.12:8080:  4
172.23.0.11:8080:  4
```

The NGINX error log contains:

```text
8 upstream timed out diagnostics
```

The error message indicates that NGINX timed out while reading the response header from the upstream.

The corresponding application records show:

```text
8 slow application requests
duration >= 2000 ms

First application timestamp:
2026-08-20T11:25:15.200Z

Last application timestamp:
2026-08-20T11:26:47.700Z
```

The application records for the correlated 504 requests eventually show HTTP 200 responses with approximately 2700 ms application duration.

Therefore, the evidence supports this sequence:

```text
Client
  |
  v
NGINX
  |
  v
Flask application
  |
  | application processing continues
  |
  | ~2.001 seconds
  v
NGINX timeout
  |
  v
Client receives 504

Later:

Flask application finishes
  |
  v
Application records HTTP 200
```

The application's 200 is an application-level outcome. The NGINX 504 is the client-facing outcome. They are not contradictory because NGINX stopped waiting before the application completed.

---

# 8. Cross-Log Correlation

## 8.1 Request that succeeded after retry

Request ID:

```text
lab-000124
```

### access.log

```text
status: 200
upstream: 172.23.0.12:8080, 172.23.0.11:8080
upstream_status: 502, 200
request_time: 0.12
```

### error.log

```text
connect() failed (111: Connection refused)
upstream: http://172.23.0.12:8080/ready
```

### application.log

```text
instance_id: app-01
status: 200
duration_ms: 120.0
```

The evidence shows:

```text
Attempt 1:
NGINX -> 172.23.0.12:8080
       -> connection refused

Attempt 2:
NGINX -> 172.23.0.11:8080
       -> app-01
       -> HTTP 200

Final client response:
HTTP 200
```

The logs do not prove why the first upstream refused the connection.

---

## 8.2 Request that resulted in a 504

Request ID:

```text
lab-000606
```

### access.log

```text
path: /records
status: 504
upstream: 172.23.0.12:8080
upstream_status: 504
request_time: 2.001
```

### error.log

```text
upstream timed out
while reading response header from upstream
upstream: http://172.23.0.12:8080/records
```

### application.log

```text
instance_id: app-02
status: 200
duration_ms: 2700
```

This proves that the backend eventually completed the request, but it exceeded the NGINX request timeout.

The client therefore received 504 even though the application eventually recorded 200.

---

# 9. Incident Timeline

The evidence supports the following chronological timeline.

| Time (UTC)        | Evidence                                               | Interpretation                                                                                 |
| ----------------- | ------------------------------------------------------ | ---------------------------------------------------------------------------------------------- |
| 11:05:02–11:09:57 | 40 access-log 502s; 59 NGINX connection-refused events | Upstream connection failures affected one backend; some requests recovered through NGINX retry |
| 11:12:09–11:15:52 | 31 Redis dependency errors and application 503s        | Application experienced Redis dependency failures                                              |
| 11:20:07–11:21:45 | 16 PostgreSQL dependency errors and application 503s   | Application experienced PostgreSQL dependency failures                                         |
| 11:25:14–11:26:47 | 8 NGINX upstream timeouts and 8 access-log 504s        | `/records` requests exceeded the NGINX timeout                                                 |
| 11:30:00          | NGINX notice                                           | Log stream/collector rotation                                                                  |

The incident therefore shows three distinct failure patterns:

```text
Connection failure
       ↓
      502

Dependency failure
       ↓
      503

Slow upstream response
       ↓
      504
```

---

# 10. Latency Analysis

For the 720 distinct client requests:

```text
Median: 54 ms
P95:    2001 ms
```

The median represents the middle request latency after sorting requests by duration.

The P95 represents the latency boundary below which approximately 95% of requests fall.

The large difference between:

```text
Median = 54 ms
P95    = 2001 ms
```

shows that normal requests were relatively fast while the slow tail was significantly higher.

The P95 is also close to the approximately 2-second NGINX timeout observed during the 504 period.

The application records show that the affected `/records` requests could take approximately 2700 ms, exceeding that proxy timeout.

---

# 11. Failure Classification

| HTTP outcome | Failure location                        | Evidence                                            |
| ------------ | --------------------------------------- | --------------------------------------------------- |
| 502          | NGINX → upstream connectivity           | `connect() failed (111: Connection refused)`        |
| 503          | Flask application → dependency          | `dependency_error` events for Redis/PostgreSQL      |
| 504          | Backend response exceeded NGINX timeout | `upstream timed out`; application duration ≈2700 ms |

## 502

Proven:

* NGINX attempted to connect to an upstream.
* The connection was refused.
* Some requests were retried successfully.

Not proven:

* Why the upstream refused the connection.

## 503

Proven:

* Flask generated 503 responses.
* Dependency errors occurred.
* Redis accounted for 31 dependency errors.
* PostgreSQL accounted for 16 dependency errors.

Not proven:

* The deeper infrastructure cause of the Redis/PostgreSQL failures.

## 504

Proven:

* NGINX waited approximately 2.001 seconds.
* The upstream did not provide the response header within that timeout.
* The applicati
