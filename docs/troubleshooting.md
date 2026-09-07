# Troubleshooting Journal

This document records investigation evidence, hypotheses, commands, results,
failed attempts, root causes, fixes, and retests for the BARQ Systems
DevOps Internship Task.

The original historical logs under `logs/` are preserved unchanged.

---

## Phase 1 — Runtime Investigation

### Investigation environment

Student GitHub baseline commit:

`65cf9a396c11a5d9dd3c146b8e8ee53e21f90438`

Working tree was clean before runtime investigation.

---

## Finding 1 — Application healthcheck failure

### Symptom

Both application containers were reported as unhealthy.

### Evidence

Docker Compose healthchecks target:

`/healthz`

The application contract provides:

`/health`

The application therefore returns HTTP 404 for the configured healthcheck
endpoint.

### Root cause

The Docker healthcheck endpoint does not match the application's implemented
health endpoint.

### Impact

The application containers are incorrectly classified as unhealthy even
though the Flask process is running.

### Planned fix

Change the container healthcheck to use `/health`.

### Verification

After the fix, Docker health status must become healthy and `/health` must
return HTTP 200.

---

## Finding 2 — Application binds only to loopback

### Symptom

NGINX cannot connect to either application container.

### Evidence

`/proc/net/tcp` inside both application containers showed:

`0100007F:1F90`

`0100007F` = `127.0.0.1`

`1F90` = port `8080`

Therefore both applications are listening on:

`127.0.0.1:8080`

NGINX requests to:

`app-01:8080`

and:

`app-02:8080`

returned:

`Connection refused`

Docker DNS resolution itself works.

### Root cause

The Flask applications bind to `127.0.0.1`, which makes them accessible only
inside their own containers.

### Impact

NGINX cannot reach either backend over the Docker frontend network.

### Planned fix

Bind the application server to:

`0.0.0.0:8080`

### Verification

From the NGINX container:

`wget -S -O- http://app-01:8080/health`

and:

`wget -S -O- http://app-02:8080/health`

must succeed.

---

## Finding 3 — NGINX upstream port mismatch

### Evidence

NGINX configuration contains:

`server app-01:8081`

and:

`server app-02:8080`

The application configuration uses port `8080`.

### Root cause

The app-01 upstream is configured for port 8081 even though the application
listens on port 8080.

### Planned fix

Configure both upstreams for port 8080.

### Verification

NGINX must successfully proxy requests to both backend instances.

---

## Finding 4 — Application to PostgreSQL port mismatch

### Symptom

The application cannot establish a TCP connection to PostgreSQL.

### Evidence

The application attempted:

`postgres:5433`

The direct TCP test returned:

`ConnectionRefusedError [Errno 111] Connection refused`

PostgreSQL is configured/listening on its standard container port:

`5432`

### Root cause

The application DATABASE_URL points to the wrong PostgreSQL container port.

### Planned fix

Use the PostgreSQL service name and container port:

`postgres:5432`

### Verification

A direct TCP test and the application's `/ready` endpoint must confirm
PostgreSQL connectivity.

---

## Finding 5 — Application to Redis port mismatch

### Symptom

The application cannot establish a TCP connection to Redis.

### Evidence

The application attempted:

`redis:6380`

The direct TCP test returned:

`ConnectionRefusedError [Errno 111] Connection refused`

Redis is configured/listening on:

`6379`

### Root cause

The application REDIS_URL points to the wrong Redis container port.

### Planned fix

Use:

`redis:6379`

### Verification

A direct TCP test and the application's `/ready` endpoint must confirm Redis
connectivity.

---

## Finding 6 — NGINX container port mapping mismatch

### Evidence

Docker reports:

`81/tcp -> host 127.0.0.1:8080`

NGINX configuration listens on:

`80`

### Root cause

The published host port maps to container port 81 while NGINX listens on
container port 80.

### Planned fix

Publish:

`127.0.0.1:8080 -> nginx:80`

### Verification

`curl http://localhost:8080/health`

must reach NGINX and the application successfully.

---

## Finding 7 — Duplicate application instance identity

### Evidence

Both application containers currently use:

`INSTANCE_ID=app-01`

### Root cause

The app-02 environment incorrectly uses the same instance identifier as
app-01.

### Planned fix

Set:

`app-01 -> INSTANCE_ID=app-01`

`app-02 -> INSTANCE_ID=app-02`

### Verification

Repeated requests through NGINX must demonstrate responses from both
distinct instance IDs.

---

## Finding 8 — NGINX violates backend network isolation

### Evidence

NGINX is attached to both frontend and backend networks.

NGINX can resolve/reach:

`postgres`

and:

`redis`

directly.

### Root cause

NGINX has unnecessary access to the backend dependency network.

### Planned fix

Attach NGINX only to the frontend network.

Applications remain connected to both frontend and backend networks.

### Verification

NGINX must reach the applications but must not be able to directly reach
PostgreSQL or Redis.

---

## Finding 9 — Unnecessary host-published ports

### Evidence

Docker reports published ports for application containers and PostgreSQL/
Redis in addition to NGINX.

The assignment requires NGINX to be the only publicly published service.

### Root cause

Host port mappings exist for internal services.

### Planned fix

Remove host port publishing from app-01, app-02, PostgreSQL, and Redis.

Only NGINX publishes host port 8080 initially.

### Verification

`docker ps` must show only the NGINX host port publication.

---

## Finding 10 — Restart policies disabled

### Evidence

All services report:

`restart=no`

### Root cause

Restart policies have not been configured.

### Planned fix

Configure appropriate restart policies according to the service
requirements.

### Verification

Compose configuration and container inspection must show the configured
restart policy.

---

## Finding 11 — No resource limits

### Evidence

All inspected services report:

`memory=0`

`cpus=0`

### Root cause

No resource limits are configured.

### Planned fix

Define reasonable CPU and memory limits for the services.

### Verification

Docker inspection must show the configured limits.

---

## Finding 12 — Application containers run as root

### Evidence

Docker inspection reports:

`app-01 user=root`

`app-02 user=root`

The Dockerfile creates a dedicated application user but switches back to
root before starting the application.

### Root cause

The intended non-root runtime user is not actually used.

### Planned fix

Run the application containers as the dedicated non-root user.

### Verification

`docker inspect` must show the non-root user configuration and runtime
behavior must remain functional.

---

## Finding 13 — PostgreSQL persistence configuration is incorrect

### Evidence

The named volume is mounted at:

`/var/lib/postgresql/backup`

The PostgreSQL data directory is instead:

`/var/lib/postgresql/data`

The supplied Compose configuration also places the data directory on tmpfs.

### Root cause

The named persistent volume is not mounted at the actual PostgreSQL data
directory.

### Impact

Database data may not survive container recreation as required.

### Planned fix

Mount the named PostgreSQL volume at the actual PostgreSQL data directory
and remove the incorrect temporary storage arrangement.

### Verification

Create a record, recreate the application and PostgreSQL containers while
retaining the named volume, then verify that the record remains.

---


---

## Finding 14 — Secret-bearing configuration copied into application image

### Evidence

The Dockerfile copies `config/app.env` into the application image:

`COPY config/app.env /srv/app.env`

The `config/app.env` file contains runtime configuration including database
credential material.

The same file is also loaded by Docker Compose as an environment file.

### Root cause

A secret-bearing runtime configuration file is included in the Docker build
context and copied into the application image.

### Security impact

Credentials may be recoverable by anyone with access to the built image or
an exported image artifact.

This violates the requirement that secrets must not be stored in images.

### Planned fix

Remove `config/app.env` from the Docker build context and do not copy it into
the image.

Keep secret-bearing configuration as runtime-only configuration.

Provide a safe `.env.example` containing only non-secret placeholders and
defaults.

### Verification

Inspect the final image filesystem without printing secret values and verify
that `config/app.env` is not embedded in the image.

---

## Finding 15 — Secret file is not explicitly protected by ignore rules

### Evidence

`.gitignore` ignores `.env` and `.env.*` while allowing `.env.example`.

`.dockerignore` also ignores `.env` and `.env.*`.

However, the secret-bearing `config/app.env` path is not explicitly excluded.

The Dockerfile currently copies this file into the image.

### Root cause

The ignore rules cover conventional `.env` files but do not explicitly
protect the actual secret-bearing configuration path used by this project.

### Planned fix

Explicitly exclude `config/app.env` from Git and Docker build contexts while
keeping `.env.example` available as a safe template.

### Verification

Confirm `config/app.env` is not tracked by Git and verify that the Docker
build context does not contain the secret-bearing file.

---

## Finding 16 — `.env.example` does not document the complete runtime configuration

### Evidence

`.env.example` currently contains only:

`PUBLIC_PORT=8080`

The application requires additional runtime configuration including:

- `APP_HOST`
- `APP_PORT`
- `APP_MESSAGE`
- `INSTANCE_ID`
- `DATABASE_URL`
- `REDIS_URL`

### Root cause

The example environment file does not provide a complete safe template for
reproducing the application's runtime configuration.

### Planned fix

Expand `.env.example` with non-secret placeholders and documented values.

No real credentials will be placed in the example file.

### Verification

A fresh setup must be reproducible using the documented environment
configuration without requiring secret values to be committed to the
repository.

---

## Finding 17 — Redis persistence is explicitly disabled

### Evidence

Redis is started with:

`--save ""`

and:

`--appendonly no`

Although `/data` may be available as a volume, Redis persistence mechanisms
are explicitly disabled by the current command.

### Root cause

Redis is configured not to persist its dataset to disk.

### Impact

Redis-backed state such as the request counter can be lost when the Redis
container is recreated.

### Planned fix

Choose and document an appropriate Redis persistence strategy for the
assignment.

### Verification

Perform a persistence test against the final configuration and record the
result.

---

## Failed diagnostic attempts

### `ps aux` inside application containers

Attempt:

`docker exec app-01 ps aux`

and:

`docker exec app-02 ps aux`

Result:

`exec: "ps": executable file not found in $PATH`

### Interpretation

This was an inconclusive diagnostic attempt caused by the minimal application
image not containing the `ps` utility. No runtime fault was inferred from
this result.

The listening socket was instead verified using `/proc/net/tcp`.

---

## Investigation principle

No runtime configuration was modified during this investigation phase.

Fixes will be applied only after the evidence has been recorded, followed by
explicit retesting.

