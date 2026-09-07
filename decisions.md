# Technical decisions

Record at least 5 decisions. Include assumptions and limits.

## Decision
- Choice:
- Why:
- Alternative:
- Trade-off:
- Evidence / commit:
- Production improvement:

Cover your base image, health checks, networks, timeouts/retries, restart/resource settings,
storage and any other meaningful choices.

## Decision: Container-to-container communication uses service names

### Decision
Use Docker Compose service names and container ports for internal
communication.

### Reason
Container-to-container communication should use Docker DNS and the
destination container's listening port rather than host-published ports.

### Applied to
- NGINX -> app-01:8080
- NGINX -> app-02:8080
- app -> postgres:5432
- app -> redis:6379

### Alternative
Use host-published ports.

### Trade-off
Host port mappings are useful for external access but unnecessarily expose
internal services and make the architecture less isolated.

---

## Decision: NGINX is the only externally published service

### Decision
Only NGINX publishes a host port.

### Reason
NGINX is the intended public entry point and reverse proxy.

### Trade-off
Internal services cannot be accessed directly from the host, but this
improves network isolation and matches the assignment architecture.

---

## Decision: Separate frontend and backend Docker networks

### Decision
NGINX connects only to frontend. Application containers connect to both
frontend and backend. PostgreSQL and Redis connect only to backend.

### Reason
The application tier needs access to both the public proxy and backend
dependencies, while NGINX does not need direct database/cache access.

### Trade-off
The topology is slightly more complex than a single network but provides
a meaningful network security boundary.
