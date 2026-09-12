# AI usage disclosure

AI assistance was used during the assessment.

## 1. Documentation and analysis

* **Tool/model:** ChatGPT
* **Purpose:** Help organize the troubleshooting journal, log analysis, security review, decisions, and required documentation.
* **Files or decisions affected:** `troubleshooting.md`, `log_analysis.md`, `decisions.md`, `security_review.md`, `AI_USAGE.md`
* **What you changed or rejected:** Used suggestions to structure and explain the work; kept only findings supported by the actual logs, repository, and tests.
* **How you independently verified it:** Compared the documentation with actual command output, logs, configuration, and Git history.
* **Related commit:** `605589b`, `bca8bbc`

## 2. Testing and troubleshooting commands

* **Tool/model:** ChatGPT
* **Purpose:** Suggest suitable Linux, Docker, Docker Compose, and container-level diagnostic/testing commands.
* **Files or decisions affected:** Troubleshooting and validation work across Dockerfile, Compose, NGINX, Flask, PostgreSQL, and Redis.
* **What you changed or rejected:** Selected commands according to each container's role, such as application health checks, PostgreSQL readiness checks, Redis `PING`, NGINX connectivity, and Docker network inspection.
* **How you independently verified it:** Executed the commands in the actual environment and used their results as evidence before making fixes.
* **Related commit:** `605589b`, `059cef5`, `b7d99b7`

## 3. Scripts and automated testing

* **Tool/model:** ChatGPT
* **Purpose:** Help design validation, backend failure/recovery, and PostgreSQL backup/restore scripts.
* **Files or decisions affected:** `validate.py`, `failure_test.py`, `backup.sh`, `restore.sh`
* **What you changed or rejected:** Adapted the scripts to the actual application behavior and task requirements rather than relying on suggested assumptions.
* **How you independently verified it:** Ran the scripts against the live Compose environment and reviewed their results, including validation, backend recovery, backup/restore, and persistence tests.
* **Related commit:** `b7d99b7`, `dbf808e`, `b3481d0`, `bca8bbc`

## 4. Technical decisions and review

* **Tool/model:** ChatGPT
* **Purpose:** Discuss Docker networking, service discovery, health/readiness, persistence, security, NGINX behavior, and CI design.
* **Files or decisions affected:** `docker-compose.yml`, `Dockerfile`, `nginx/nginx.conf`, CI workflow, `decisions.md`, `security_review.md`
* **What you changed or rejected:** Used AI as a reviewer and considered alternatives and trade-offs; final choices were based on the assessment requirements and observed behavior.
* **How you independently verified it:** Tested the resulting configuration locally and reviewed the final repository state and Git history.
* **Related commit:** `059cef5`, `56ac3d8`

## Independence statement

AI was used for guidance, explanation, review, and documentation support. The author executed and verified the relevant commands and tests, made the final decisions, and is responsible for understanding and demonstrating the submitted work.