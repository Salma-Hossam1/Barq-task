# Troubleshooting journal

Keep chronological entries. Copy this block for each meaningful investigation.

The original historical logs under `logs/` are preserved unchanged.

---

## Entry 1 — Application healthcheck failure

- Date / time: Not recorded during the original investigation.

- Symptom:
  Both application containers were reported as unhealthy.

- Hypothesis:
  The configured Docker healthcheck may target an endpoint that the Flask
  application does not implement.

- Command or test:
  Inspected the Docker Compose healthcheck configuration and the application's
  endpoint contract.

- Actual output:
  The Compose healthcheck targeted `/healthz`.

  The application contract provides `/health`.

  The application therefore returns HTTP 404 for the configured healthcheck
  endpoint.

- Failed attempt and what changed your thinking:
  No failed remediation attempt was recorded during this investigation.
  The endpoint mismatch established the cause.

- Root cause:
  The Docker healthcheck endpoint does not match the application's
  implemented health endpoint.

- Fix:
  Planned during Phase 1: change the healthcheck endpoint from `/healthz` to
  `/health`.

  The implementation was deferred until after the investigation.

- Retest evidence:
  Not performed during Phase 1.

  Planned verification: Docker reports the application containers as healthy
  and `/health` returns HTTP 200.

- Related commit:
  `65cf9a396c11a5d9dd3c146b8e8ee53e21f90438` — investigation baseline.

- Remaining uncertainty:
  Final runtime health status must be confirmed after the Phase 2 fix.

---

## Entry 2 — Application binds only to loopback

- Date / time: Not recorded during the original investigation.

- Symptom:
  NGINX could not connect to the application containers.

- Hypothesis:
  The Flask application may be listening only on the container loopback
  interface instead of the Docker network interface.

- Command or test:
  Inspected `/proc/net/tcp` inside both application containers and tested
  connectivity from NGINX to the application service names.

- Actual output:
  `/proc/net/tcp` inside both application containers showed:

  `0100007F:1F90`

  `0100007F` corresponds to `127.0.0.1`.

  `1F90` corresponds to port `8080`.

  Therefore both applications were listening on:

  `127.0.0.1:8080`

  NGINX requests to:

  `app-01:8080`

  and:

  `app-02:8080`

  returned:

  `Connection refused`

  Docker DNS resolution itself worked.

- Failed attempt and what changed my thinking:
  NGINX connectivity failed even though Docker service-name resolution worked.
  The socket inspection showed that the process was listening only on
  loopback, separating the networking problem from DNS resolution.

- Root cause:
  The Flask applications bind to `127.0.0.1`, making them accessible only
  inside their own containers.

- Fix:
  Planned during Phase 1: bind the application server to `0.0.0.0:8080`.

- Retest evidence:
  Not performed during Phase 1.

  Planned verification from NGINX:

  `wget -S -O- http://app-01:8080/health`

  `wget -S -O- http://app-02:8080/health`

- Related commit:
  `65cf9a396c11a5d9dd3c146b8e8ee53e21f90438` — investigation baseline.

- Remaining uncertainty:
  Final backend connectivity must be confirmed after the binding change.

---

## Entry 3 — NGINX upstream port mismatch

- Date / time: Not recorded during the original investigation.

- Symptom:
  NGINX could not correctly proxy to both application instances.

- Hypothesis:
  One of the NGINX upstream ports may not match the port used by the
  application containers.

- Command or test:
  Inspected the NGINX upstream configuration and compared it with the
  application port configuration.

- Actual output:
  NGINX configured:

  `server app-01:8081`

  and:

  `server app-02:8080`

  The application configuration uses port `8080`.

- Failed attempt and what changed my thinking:
  The mismatch was found through configuration inspection; no separate
  remediation attempt was recorded.

- Root cause:
  The `app-01` upstream was configured for port `8081` even though the
  application listens on port `8080`.

- Fix:
  Planned during Phase 1: configure both NGINX upstreams for port `8080`.

- Retest evidence:
  Not performed during Phase 1.

  Planned verification: NGINX successfully proxies requests to both backend
  instances.

- Related commit:
  `65cf9a396c11a5d9dd3c146b8e8ee53e21f90438` — investigation baseline.

- Remaining uncertainty:
  Final proxying behavior must be confirmed after the upstream correction.

---

## Entry 4 — Application to PostgreSQL port mismatch

- Date / time: Not recorded during the original investigation.

- Symptom:
  The application could not establish a TCP connection to PostgreSQL.

- Hypothesis:
  The application's PostgreSQL connection URL may specify the wrong
  container port.

- Command or test:
  Inspected the application's database connection configuration and tested
  direct TCP connectivity to PostgreSQL.

- Actual output:
  The application attempted:

  `postgres:5433`

  The direct TCP test returned:

  `ConnectionRefusedError [Errno 111] Connection refused`

  PostgreSQL is configured/listening on its standard container port:

  `5432`

- Failed attempt and what changed my thinking:
  The direct connection to `postgres:5433` was refused while PostgreSQL was
  listening on `5432`, confirming that the failure was a port mismatch rather
  than a PostgreSQL process failure.

- Root cause:
  The application `DATABASE_URL` points to the wrong PostgreSQL container
  port.

- Fix:
  Planned during Phase 1: use the PostgreSQL service name and container port:

  `postgres:5432`

- Retest evidence:
  Not performed during Phase 1.

  Planned verification: a direct TCP test and the application's `/ready`
  endpoint confirm PostgreSQL connectivity.

- Related commit:
  `65cf9a396c11a5d9dd3c146b8e8ee53e21f90438` — investigation baseline.

- Remaining uncertainty:
  Database readiness must be confirmed after the configuration change.

---

## Entry 5 — Application to Redis port mismatch

- Date / time: Not recorded during the original investigation.

- Symptom:
  The application could not establish a TCP connection to Redis.

- Hypothesis:
  The application's Redis connection URL may specify the wrong container
  port.

- Command or test:
  Inspected the application's Redis connection configuration and tested
  direct TCP connectivity to Redis.

- Actual output:
  The application attempted:

  `redis:6380`

  The direct TCP test returned:

  `ConnectionRefusedError [Errno 111] Connection refused`

  Redis is configured/listening on:

  `6379`

- Failed attempt and what changed my thinking:
  The direct connection to `redis:6380` was refused while Redis was listening
  on `6379`, establishing a port mismatch.

- Root cause:
  The application `REDIS_URL` points to the wrong Redis container port.

- Fix:
  Planned during Phase 1: use:

  `redis:6379`

- Retest evidence:
  Not performed during Phase 1.

  Planned verification: a direct TCP test and the application's `/ready`
  endpoint confirm Redis connectivity.

- Related commit:
  `65cf9a396c11a5d9dd3c146b8e8ee53e21f90438` — investigation baseline.

- Remaining uncertainty:
  Redis readiness must be confirmed after the configuration change.

---

## Entry 6 — NGINX container port mapping mismatch

- Date / time: Not recorded during the original investigation.

- Symptom:
  The host port was published, but requests did not reach the NGINX
  listener as intended.

- Hypothesis:
  The Docker host-to-container port mapping may not match the port on which
  NGINX listens.

- Command or test:
  Inspected the Docker port mapping and NGINX listener configuration.

- Actual output:
  Docker reported:

  `81/tcp -> host 127.0.0.1:8080`

  NGINX configuration listens on:

  `80`

- Failed attempt and what changed my thinking:
  The mismatch between the published container port (`81`) and the actual
  NGINX listener (`80`) established the cause.

- Root cause:
  The published host port maps to container port `81` while NGINX listens on
  container port `80`.

- Fix:
  Planned during Phase 1: publish:

  `127.0.0.1:8080 -> nginx:80`

- Retest evidence:
  Not performed during Phase 1.

  Planned verification:

  `curl http://localhost:8080/health`

- Related commit:
  `65cf9a396c11a5d9dd3c146b8e8ee53e21f90438` — investigation baseline.

- Remaining uncertainty:
  Final end-to-end HTTP routing must be confirmed after the mapping change.

---

## Entry 7 — Duplicate application instance identity

- Date / time: Not recorded during the original investigation.

- Symptom:
  The two backend instances did not have distinct configured identities.

- Hypothesis:
  `app-02` may have inherited or been assigned the same `INSTANCE_ID` as
  `app-01`.

- Command or test:
  Inspected the Compose environment configuration for both application
  services.

- Actual output:
  Both application containers were configured with:

  `INSTANCE_ID=app-01`

- Failed attempt and what changed my thinking:
  No failed remediation attempt was recorded. Configuration inspection
  directly showed the duplicate identity.

- Root cause:
  The `app-02` environment incorrectly uses the same instance identifier as
  `app-01`.

- Fix:
  Planned during Phase 1:

  `app-01 -> INSTANCE_ID=app-01`

  `app-02 -> INSTANCE_ID=app-02`

- Retest evidence:
  Not performed during Phase 1.

  Planned verification: repeated requests through NGINX demonstrate responses
  from both distinct instance IDs.

- Related commit:
  `65cf9a396c11a5d9dd3c146b8e8ee53e21f90438` — investigation baseline.

- Remaining uncertainty:
  Load-balancing behavior must be proven through repeated requests after
  the identity correction.

---

## Entry 8 — NGINX violates backend network isolation

- Date / time: Not recorded during the original investigation.

- Symptom:
  NGINX had direct network access to backend dependency services.

- Hypothesis:
  NGINX may be attached to the backend network even though it only needs to
  communicate with the application containers.

- Command or test:
  Inspected Compose network attachments and tested NGINX access to the
  backend service names.

- Actual output:
  NGINX was attached to both frontend and backend networks.

  NGINX could resolve/reach:

  `postgres`

  and:

  `redis`

  directly.

- Failed attempt and what changed my thinking:
  The direct accessibility of PostgreSQL and Redis from NGINX showed that
  network attachment was broader than required.

- Root cause:
  NGINX has unnecessary access to the backend dependency network.

- Fix:
  Planned during Phase 1: attach NGINX only to the frontend network.

  Applications remain connected to both frontend and backend networks.

- Retest evidence:
  Not performed during Phase 1.

  Planned verification: NGINX reaches the applications but does not have
  direct network access to PostgreSQL or Redis.

- Related commit:
  `65cf9a396c11a5d9dd3c146b8e8ee53e21f90438` — investigation baseline.

- Remaining uncertainty:
  Final network membership and isolation must be verified after the Compose
  network changes.

---

## Entry 9 — Unnecessary host-published ports

- Date / time: Not recorded during the original investigation.

- Symptom:
  Internal services had host port publications in addition to NGINX.

- Hypothesis:
  PostgreSQL, Redis, or application services may expose host ports that are
  unnecessary for the required architecture.

- Command or test:
  Inspected Docker port publications for the running services.

- Actual output:
  Docker reported published ports for application containers and
  PostgreSQL/Redis in addition to NGINX.

  The assignment requires NGINX to be the only publicly published service.

- Failed attempt and what changed my thinking:
  No failed remediation attempt was recorded.

- Root cause:
  Host port mappings exist for internal services that should communicate
  through Docker networks.

- Fix:
  Planned during Phase 1: remove host port publishing from `app-01`,
  `app-02`, PostgreSQL, and Redis.

  Only NGINX publishes host port `8080` initially.

- Retest evidence:
  Not performed during Phase 1.

  Planned verification: `docker ps` shows only the NGINX host port publication.

- Related commit:
  `65cf9a396c11a5d9dd3c146b8e8ee53e21f90438` — investigation baseline.

- Remaining uncertainty:
  Final published-port state must be verified after the Compose changes.

---

## Entry 10 — Restart policies disabled

- Date / time: Not recorded during the original investigation.

- Symptom:
  Services were configured without automatic restart behavior.

- Hypothesis:
  The Compose services may all use the default/no-restart policy.

- Command or test:
  Inspected the configured restart policies.

- Actual output:
  All services reported:

  `restart=no`

- Failed attempt and what changed my thinking:
  No failed remediation attempt was recorded.

- Root cause:
  Restart policies had not been configured.

- Fix:
  Planned during Phase 1: configure appropriate restart policies according
  to the service requirements.

- Retest evidence:
  Not performed during Phase 1.

  Planned verification: Compose configuration and container inspection show
  the configured restart policy.

- Related commit:
  `65cf9a396c11a5d9dd3c146b8e8ee53e21f90438` — investigation baseline.

- Remaining uncertainty:
  The final policy for each service must be verified after implementation.

---

## Entry 11 — No resource limits

- Date / time: Not recorded during the original investigation.

- Symptom:
  The services had no configured CPU or memory limits.

- Hypothesis:
  Compose resource limits may be absent.

- Command or test:
  Inspected the resource configuration for the running services.

- Actual output:
  Inspected services reported:

  `memory=0`

  `cpus=0`

- Failed attempt and what changed my thinking:
  No failed remediation attempt was recorded.

- Root cause:
  No resource limits were configured.

- Fix:
  Planned during Phase 1: define reasonable CPU and memory limits for the
  services.

- Retest evidence:
  Not performed during Phase 1.

  Planned verification: Docker inspection shows the configured resource
  limits.

- Related commit:
  `65cf9a396c11a5d9dd3c146b8e8ee53e21f90438` — investigation baseline.

- Remaining uncertainty:
  Final resource values must be verified against the Compose configuration.

---

## Entry 12 — Application containers run as root

- Date / time: Not recorded during the original investigation.

- Symptom:
  The application containers run as the root user.

- Hypothesis:
  The Dockerfile may create a non-root user but fail to use it at runtime.

- Command or test:
  Inspected the Dockerfile and Docker container user configuration.

- Actual output:
  Docker inspection reported:

  `app-01 user=root`

  `app-02 user=root`

  The Dockerfile creates a dedicated application user but switches back to
  root before starting the application.

- Failed attempt and what changed my thinking:
  No failed remediation attempt was recorded.

- Root cause:
  The intended non-root runtime user is not actually used.

- Fix:
  Planned during Phase 1: run the application containers as the dedicated
  non-root user.

- Retest evidence:
  Not performed during Phase 1.

  Planned verification: `docker inspect` shows the non-root user
  configuration and the application remains functional.

- Related commit:
  `65cf9a396c11a5d9dd3c146b8e8ee53e21f90438` — investigation baseline.

- Remaining uncertainty:
  Runtime behavior must be verified after switching to the non-root user.

---

## Entry 13 — PostgreSQL persistence configuration is incorrect

- Date / time: Not recorded during the original investigation.

- Symptom:
  PostgreSQL's persistent volume did not correspond to its actual data
  directory.

- Hypothesis:
  The named volume may be mounted at the wrong PostgreSQL path while the
  actual database directory uses temporary storage.

- Command or test:
  Inspected the PostgreSQL Compose volume mounts and the PostgreSQL data
  directory configuration.

- Actual output:
  The named volume was mounted at:

  `/var/lib/postgresql/backup`

  The PostgreSQL data directory is:

  `/var/lib/postgresql/data`

  The supplied Compose configuration also places the data directory on
  tmpfs.

- Failed attempt and what changed my thinking:
  No failed remediation attempt was recorded.

  The mount-path mismatch showed that the named volume was not protecting
  the live PostgreSQL data directory.

- Root cause:
  The named persistent volume is not mounted at the actual PostgreSQL data
  directory.

- Fix:
  Planned during Phase 1: mount the named PostgreSQL volume at the actual
  PostgreSQL data directory and remove the incorrect temporary storage
  arrangement.

- Retest evidence:
  Not performed during Phase 1.

  Planned verification: create a record, recreate the application and
  PostgreSQL containers while retaining the named volume, then verify that
  the record remains.

- Related commit:
  `65cf9a396c11a5d9dd3c146b8e8ee53e21f90438` — investigation baseline.

- Remaining uncertainty:
  Persistence must be proven through an actual recreate-and-read test.

---

## Entry 14 — Secret-bearing configuration copied into application image

- Date / time: Not recorded during the original investigation.

- Symptom:
  A runtime environment file containing credential material was included in
  the application image build.

- Hypothesis:
  The Dockerfile may copy the runtime environment file into the image.

- Command or test:
  Inspected the Dockerfile and the runtime environment configuration.

- Actual output:
  The Dockerfile contained:

  `COPY config/app.env /srv/app.env`

  The `config/app.env` file contains runtime configuration including database
  credential material.

  The same file is also loaded by Docker Compose as an environment file.

- Failed attempt and what changed my thinking:
  No failed remediation attempt was recorded.

- Root cause:
  A secret-bearing runtime configuration file is included in the Docker
  build context and copied into the application image.

- Fix:
  Planned during Phase 1: remove `config/app.env` from the Docker image build
  and keep secret-bearing configuration runtime-only.

  Provide a safe `.env.example` containing only non-secret placeholders and
  defaults.

- Retest evidence:
  Not performed during Phase 1.

  Planned verification: inspect the final image filesystem without printing
  secret values and confirm that `config/app.env` is not embedded in the
  image.

- Related commit:
  `65cf9a396c11a5d9dd3c146b8e8ee53e21f90438` — investigation baseline.

- Remaining uncertainty:
  The final image must be inspected after the Dockerfile change.

---

## Entry 15 — Secret file is not explicitly protected by ignore rules

- Date / time: Not recorded during the original investigation.

- Symptom:
  The project's actual runtime secret path was not explicitly protected by
  Git and Docker ignore rules.

- Hypothesis:
  Existing `.env` patterns may not cover `config/app.env`.

- Command or test:
  Inspected `.gitignore` and `.dockerignore` and checked the tracking state
  of `config/app.env`.

- Actual output:
  `.gitignore` ignored `.env` and `.env.*` while allowing `.env.example`.

  `.dockerignore` also ignored `.env` and `.env.*`.

  However, the secret-bearing path `config/app.env` was not explicitly
  excluded.

  `config/app.env` was tracked in the supplied repository history.

- Failed attempt and what changed my thinking:
  No failed remediation attempt was recorded.

  The tracking check established that the actual project secret file required
  an explicit rule.

- Root cause:
  The ignore rules covered conventional `.env` paths but did not explicitly
  protect the actual secret-bearing configuration path used by this project.

- Fix:
  Planned during Phase 1: explicitly exclude `config/app.env` and other
  local secret configuration from Git and Docker build contexts.

- Retest evidence:
  Not performed during Phase 1.

  Planned verification: confirm the secret file is ignored by Git and Docker
  and is not included in the Docker build context.

- Related commit:
  `65cf9a396c11a5d9dd3c146b8e8ee53e21f90438` — investigation baseline.

- Remaining uncertainty:
  Historical repository exposure remains a separate security-review concern;
  current working-tree protection must be verified after the Phase 2 changes.

---

## Entry 16 — `.env.example` does not document complete runtime configuration

- Date / time: Not recorded during the original investigation.

- Symptom:
  The example environment file did not document the complete runtime
  configuration needed to reproduce the application.

- Hypothesis:
  `.env.example` may contain only the public port rather than the complete
  non-secret runtime configuration.

- Command or test:
  Inspected `.env.example` and compared it with the application's runtime
  configuration.

- Actual output:
  `.env.example` contained only:

  `PUBLIC_PORT=8080`

  The application requires additional runtime configuration including:

  `APP_HOST`

  `APP_PORT`

  `APP_MESSAGE`

  `INSTANCE_ID`

  `DATABASE_URL`

  `REDIS_URL`

- Failed attempt and what changed my thinking:
  No failed remediation attempt was recorded.

- Root cause:
  The example environment file does not provide a complete safe template for
  reproducing the application's runtime configuration.

- Fix:
  Planned during Phase 1: expand `.env.example` with non-secret placeholders
  and documented values.

  No real credentials will be placed in the example file.

- Retest evidence:
  Not performed during Phase 1.

  Planned verification: a fresh setup can reproduce the documented runtime
  configuration without requiring secret values to be committed.

- Related commit:
  `65cf9a396c11a5d9dd3c146b8e8ee53e21f90438` — investigation baseline.

- Remaining uncertainty:
  The final example file must be reviewed against the completed Compose
  configuration.

---

## Entry 17 — Redis persistence is explicitly disabled

- Date / time: Not recorded during the original investigation.

- Symptom:
  Redis was configured without persistent dataset storage.

- Hypothesis:
  The Redis command may explicitly disable both snapshot and AOF
  persistence.

- Command or test:
  Inspected the Redis Compose command and volume configuration.

- Actual output:
  Redis was started with:

  `--save ""`

  and:

  `--appendonly no`

  Although `/data` may be available as a volume, Redis persistence mechanisms
  were explicitly disabled by the current command.

- Failed attempt and what changed my thinking:
  No failed remediation attempt was recorded.

  The Redis command itself established that persistence was disabled.

- Root cause:
  Redis was configured not to persist its dataset to disk.

- Fix:
  Planned during Phase 1: choose and document an appropriate Redis
  persistence strategy for the assignment.

- Retest evidence:
  Not performed during Phase 1.

  Planned verification: perform a persistence test against the final
  configuration and record the result.

- Related commit:
  `65cf9a396c11a5d9dd3c146b8e8ee53e21f90438` — investigation baseline.

- Remaining uncertainty:
  Redis persistence must be proven after implementing the persistence
  strategy.

---

## Entry 18 — Minimal image diagnostic: `ps` unavailable

- Date / time: Not recorded during the original investigation.

- Symptom:
  A process-inspection diagnostic command could not be executed inside the
  application containers.

- Hypothesis:
  The minimal application image may not include the `ps` utility.

- Command or test:
  Attempted:

  `docker exec app-01 ps aux`

  `docker exec app-02 ps aux`

- Actual output:
  Both attempts returned:

  `exec: "ps": executable file not found in $PATH`

- Failed attempt and what changed my thinking:
  The failure showed that `ps` was unavailable in the minimal image. This
  meant the command could not be used to inspect the running process and was
  therefore inconclusive as a runtime diagnostic.

  The investigation switched to `/proc/net/tcp` to inspect the listening
  socket without installing additional tools or modifying the image.

- Root cause:
  The minimal application image does not contain the `ps` utility.

- Fix:
  No runtime fix was required. The diagnostic method was changed to use the
  available `/proc/net/tcp` interface.

- Retest evidence:
  `/proc/net/tcp` successfully provided the required listening-socket
  evidence.

- Related commit:
  `65cf9a396c11a5d9dd3c146b8e8ee53e21f90438` — investigation baseline.

- Remaining uncertainty:
  None regarding this diagnostic limitation.

---

## Investigation principle

No runtime configuration was modified during the Phase 1 investigation.

The investigation first established symptoms, tested hypotheses, and recorded
evidence. Configuration fixes were intentionally deferred until after the
evidence had been recorded.

Phase 2 implementation and subsequent runtime verification will be recorded
as new chronological entries rather than rewriting the Phase 1 evidence.


---

## Entry 19 / 9 Sep / 4:00

* Symptom:

  * `/ready` returned `503 SERVICE UNAVAILABLE`.
  * The response reported `postgres: unavailable` while `redis: ready`.

* Hypothesis:

  * The application could reach the PostgreSQL service, but the database credentials used by the application might not match the credentials configured for PostgreSQL.

* Command or test:

  * Checked PostgreSQL container logs and application database configuration.
  * Compared the password configured in `config/app.env` with the PostgreSQL password in `config/postgres.env` without exposing either value.

* Actual output:

  * PostgreSQL logs showed:
    `FATAL: password authentication failed for user "barq_app"`
  * PostgreSQL was listening on port `5432` and the database was otherwise healthy.
  * Safe credential comparison reported:
    `PASSWORDS DO NOT MATCH`
  * PostgreSQL logs also showed:
    `PostgreSQL Database directory appears to contain a database; Skipping initialization`

* Failed attempt and what changed your thinking:

  * Attempted to synchronize the existing PostgreSQL role password with the configured PostgreSQL password using `ALTER ROLE`; PostgreSQL returned `ALTER ROLE`.
  * A subsequent direct application database test still failed with password authentication errors.
  * This showed that the existing database state and the application's configured `DATABASE_URL` were not yet synchronized, rather than indicating a PostgreSQL availability or networking problem.

* Root cause:

  * Credential drift between the application's `DATABASE_URL` and the PostgreSQL credential.
  * The PostgreSQL named volume was already initialized, so changing PostgreSQL environment variables did not automatically recreate or reinitialize the existing database credentials.

* Fix:

  * Synchronized the password used by the application's `DATABASE_URL` with the PostgreSQL credential.
  * Recreated only `app-01` and `app-02` so they loaded the corrected environment configuration:
    `docker compose up -d --force-recreate app-01 app-02`
  * The PostgreSQL volume was preserved.

* Retest evidence:

  * Direct application database test:
    `DATABASE: SUCCESS`
  * `/ready` subsequently returned:
    `HTTP/1.1 200 OK`
  * Response reported:
    `postgres: ready`
    `redis: ready`
  * The application was therefore able to authenticate to PostgreSQL successfully.

* Related commit:

  * Pending — commit will be recorded after the troubleshooting-journal update is committed.

* Remaining uncertainty:

  * No remaining runtime uncertainty for this specific PostgreSQL authentication failure.
  * The persistence behavior of the named PostgreSQL volume will be verified separately during the required persistence test.
