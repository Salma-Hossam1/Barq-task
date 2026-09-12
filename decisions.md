# Technical Decisions

This document records the main technical decisions made while repairing and completing the BARQ Systems assessment environment. Each decision includes the reasoning, alternatives, trade-offs, evidence, and a production improvement.

---

## Decision: Container-to-container communication uses service names

### Decision

Use Docker Compose service names and container ports for internal communication.

### Choice

Internal communication uses:

- NGINX → `app-01:8080`
- NGINX → `app-02:8080`
- Application → `postgres:5432`
- Application → `redis:6379`

### Why

Container-to-container communication should use Docker's internal DNS and the destination container's listening port rather than host-published ports.

This keeps internal communication independent of host port mappings and allows containers to be recreated without depending on fixed container IP addresses.

### Alternative

Use host-published ports for communication between services.

### Trade-off

Host port mappings can be useful for external access, but using them for internal communication unnecessarily exposes services and makes the architecture less isolated.

### Evidence / commit

The incorrect application and NGINX ports were identified during investigation and corrected in:

`059cef5` — `fix: repair container networking and runtime configuration`

The resulting communication paths were verified by:

`b7d99b7` — `verify: implement automated environment validation`

### Production improvement

Use service discovery through the platform's native DNS/service mechanism and avoid coupling application configuration to infrastructure IP addresses.

---

## Decision: NGINX is the only externally published service

### Decision

Only NGINX publishes a host port.

### Choice

The final topology exposes:

`host:8080 → NGINX:80`

The Flask applications, PostgreSQL, and Redis have no host-published ports.

### Why

NGINX is the intended public entry point and reverse proxy. Internal services should only be reachable through the Docker networks they require.

### Alternative

Publish application, PostgreSQL, and Redis ports directly on the host.

### Trade-off

Internal services cannot be accessed directly from the host, but this improves network isolation and matches the assignment architecture.

### Evidence / commit

The unnecessary host port mappings were removed in:

`059cef5` — `fix: repair container networking and runtime configuration`

The final exposure was checked by:

`b7d99b7` — `verify: implement automated environment validation`

### Production improvement

Use a dedicated ingress/load-balancing layer in front of multiple application instances and keep databases and caches on private networks with no public exposure.

---

## Decision: Separate frontend and backend Docker networks

### Decision

Use separate frontend and backend Docker networks.

### Choice

- NGINX → `frontend`
- Applications → `frontend` + `backend`
- PostgreSQL → `backend`
- Redis → `backend`

NGINX is intentionally not connected to the backend network.

### Why

The application tier needs access to both the reverse proxy network and backend dependencies, while NGINX does not need direct access to PostgreSQL or Redis.

This creates a meaningful network boundary between the public-facing proxy and internal dependencies.

### Alternative

Place all services on a single Docker network.

### Trade-off

The topology is slightly more complex than a single network, but provides better isolation and makes the intended communication paths explicit.

### Evidence / commit

The network topology was corrected in:

`059cef5` — `fix: repair container networking and runtime configuration`

The validator checks that NGINX is not attached to the backend network:

`b7d99b7` — `verify: implement automated environment validation`

### Production improvement

Use stronger network policies and segmentation in a production orchestration platform, combined with service-level authentication and authorization.

---

## Decision: Flask listens on the container network interface

### Decision

Configure the Flask application to listen on `0.0.0.0:8080` rather than `127.0.0.1:8080`.

### Why

`127.0.0.1` makes the service reachable only from inside its own container. NGINX is a separate container and therefore cannot connect to a loopback-only listener.

The application must listen on the container network interface so NGINX can reach it.

### Alternative

Keep Flask bound to `127.0.0.1` and expose it through another local proxy inside each application container.

### Trade-off

Binding to `0.0.0.0` makes the application reachable from other containers on networks to which it is attached. Network segmentation is therefore important.

### Evidence / commit

The original loopback binding was confirmed during investigation and corrected in:

`059cef5` — `fix: repair container networking and runtime configuration`

Public endpoint and backend routing were verified by:

`b7d99b7`

### Production improvement

Use a production-grade WSGI server and enforce network-level and application-level access controls around the application tier.

---

## Decision: Health and readiness checks answer different questions

### Decision

Use `/health` for application health and `/ready` for dependency-aware readiness.

### Why

A running application process does not necessarily mean the application can successfully serve requests requiring PostgreSQL and Redis.

The distinction allows the environment to determine:

- whether the application process is alive;
- whether required dependencies are reachable and usable.

### Alternative

Use only one health endpoint.

### Trade-off

Maintaining two endpoints adds a small amount of application and configuration complexity, but gives clearer operational semantics.

### Evidence / commit

The original healthcheck incorrectly used `/healthz` while the application implemented `/health`. This was corrected in:

`059cef5`

The resulting health/readiness behavior was verified by:

`b7d99b7`

### Production improvement

Use platform-native liveness and readiness probes with carefully bounded dependency checks and monitoring around probe failures.

---

## Decision: NGINX uses bounded timeouts and upstream retry

### Decision

Configure NGINX with explicit connection/read timeouts and allow eligible upstream failures to retry another application instance.

### Why

With multiple application instances, a temporary connection failure should not necessarily become a client-visible outage when another healthy backend is available.

Timeouts also prevent requests from remaining blocked indefinitely.

### Alternative

Use no upstream retry and allow failed requests to immediately return an error.

### Trade-off

Retries can improve availability but may increase latency when the first backend fails. Aggressive retries can also amplify load during an incident, so retry behavior must remain bounded.

### Evidence / commit

The final NGINX configuration uses bounded proxy timeouts and upstream retry behavior.

The historical log analysis also demonstrated requests where an initial `502` was followed by a successful upstream response.

The live failure/recovery test confirmed continued successful traffic when one backend was stopped:

`dbf808e` — `test: verify backend failure and recovery`

### Production improvement

Use carefully tuned retry budgets, circuit breaking, load-balancer health checks, and observability around retry rates.

---

## Decision: Configure restart behavior and resource limits

### Decision

Configure appropriate restart behavior and CPU/memory limits for the Compose services.

### Why

A service failure should not necessarily leave the workload permanently stopped, while resource limits reduce the risk of a single container consuming excessive host resources.

### Alternative

Run containers without restart policies or resource constraints.

### Trade-off

Restart policies improve recovery but can cause repeated restart loops if the underlying fault is not addressed. Resource limits improve isolation but can terminate or throttle workloads if limits are set too aggressively.

### Evidence / commit

Restart behavior and resource limits were added in:

`059cef5` — `fix: repair container networking and runtime configuration`

### Production improvement

Use orchestration-level restart policies, resource requests/limits, autoscaling, and alerting based on restart and resource-utilization metrics.

---

## Decision: Use persistent storage for PostgreSQL and Redis

### Decision

Use named Docker volumes for PostgreSQL and Redis persistent data.

### Choice

- PostgreSQL → `postgres-data:/var/lib/postgresql/data`
- Redis → `redis-data:/data`
- Redis persistence → AOF with `appendfsync everysec`

### Why

Database and cache state should not depend on the lifecycle of an individual container.

### Alternative

Keep state only inside the container filesystem.

### Trade-off

Named volumes preserve state across container recreation, but they remain local to the Docker host and therefore do not provide distributed storage or disaster recovery by themselves.

### Evidence / commit

The PostgreSQL volume configuration was corrected in:

`059cef5`

Persistence was subsequently verified by recreating PostgreSQL and the application containers without removing the named volume. The previously created record remained available.

Documentation of the verification was added in:

`bca8bbc` — `docs: record backup and persistence verification`

### Production improvement

Use managed/distributed persistent storage, automated backups, replication, and tested disaster-recovery procedures.

---

## Decision: Keep secrets outside the image and source-controlled configuration

### Decision

Use a dedicated secrets manager or platform-native secret store instead of local environment files, with credential rotation and least-privilege access.

### Why

Secrets embedded in images or tracked configuration can be exposed through source history, image layers, or repository access.

### Alternative

Copy `config/app.env` into the Docker image during build.

### Trade-off

Runtime configuration must be provided separately when starting the environment, but this keeps secrets out of the image build.

### Evidence / commit

The Dockerfile was changed to stop copying `config/app.env`, and the configuration files were removed from the current Git index and added to ignore rules.

A safe `.env.example` was added containing placeholders only.

These changes were implemented in:

`059cef5` — `fix: repair container networking and runtime configuration`

### Limitation

The supplied starter repository already contained `config/app.env` in its historical Git commits. Removing the file from the current index does not erase those historical contents.

The affected credentials should therefore be rotated before final submission.

### Production improvement

Use a dedicated secrets manager or platform-native secret store rather than environment files, with credential rotation and least-privilege access.

---

## Decision: Run the application as a non-root user

### Decision

Run the Flask application using a dedicated non-root `app` user.

### Why

The application does not require root privileges. Running as a non-root user reduces the privileges available if the application is compromised.

### Alternative

Run the application as the default root user.

### Trade-off

A non-root container requires correct file ownership and permissions during image construction, but provides a safer default execution context.

### Evidence / commit

The Dockerfile creates the `app` user and switches to it using `USER app`.

Implemented in:

`059cef5` — `fix: repair container networking and runtime configuration`

### Production improvement

Combine non-root execution with a read-only root filesystem where practical, dropped Linux capabilities, seccomp/AppArmor profiles, and stronger runtime isolation.

---

## Decision: Retain the supplied Python slim base image

### Decision

Retain the supplied `python:3.12-slim-bookworm` base image for the Flask application.

### Why

The application requires Python 3.12, and the slim Bookworm image provides the required Python runtime with a smaller footprint than the full Python image.

The baseline inspection showed that this image was already part of the supplied starter environment, so no unnecessary base-image migration was introduced.

### Alternative

Replace it with the full Python image or another Python/Linux base image.

### Trade-off

The slim image reduces unnecessary packages and image size, but it also contains fewer diagnostic/system utilities. During investigation, for example, `ps` was unavailable inside the application container.

### Evidence / commit

Baseline verification:

`65cf9a3` — supplied starter Dockerfile already used `python:3.12-slim-bookworm`.

The final image was successfully built and used by the Compose environment and CI pipeline.

### Production improvement

Regularly update the base image, scan it for vulnerabilities, and use an approved minimal base-image strategy with a defined patch/update process.
