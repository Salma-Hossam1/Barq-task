#!/usr/bin/env python3

"""Validate the BARQ assessment environment."""

import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request


COMMAND_TIMEOUT = 10
HTTP_TIMEOUT = 3

passed = 0
failed = 0

def get_base_url():
    """Use BASE_URL when supplied, otherwise derive the published port."""
    explicit = os.getenv("BASE_URL")
    if explicit:
        return explicit.rstrip("/")

    port = "8080"
    if os.path.exists(".env"):
        with open(".env", encoding="utf-8") as env_file:
            for line in env_file:
                line = line.strip()
                if line.startswith("PUBLIC_PORT="):
                    port = line.split("=", 1)[1].strip()
                    break

    return f"http://127.0.0.1:{port}"


BASE_URL = get_base_url()

def pass_check(message):
    """Record and print a successful check."""
    global passed
    passed += 1
    print(f"PASS: {message}")


def fail_check(message):
    """Record and print a failed check."""
    global failed
    failed += 1
    print(f"FAIL: {message}")


def run_command(command, timeout=COMMAND_TIMEOUT):
    """Run a command and return its completed-process result."""
    try:
        return subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except (subprocess.TimeoutExpired, OSError):
        return None

def wait_for_command(command, description, attempts=10, delay=2):
    """Wait for a command to succeed, with a bounded retry period."""
    for _ in range(attempts):
        result = run_command(command)

        if result is not None and result.returncode == 0:
            pass_check(description)
            return True

        time.sleep(delay)

    fail_check(description)
    return False

def check_command(description, command):
    """PASS when the supplied command exits successfully."""
    result = run_command(command)

    if result is not None and result.returncode == 0:
        pass_check(description)
        return True

    fail_check(description)
    return False


def http_get(path):
    """Perform a bounded HTTP GET and return status/body."""
    try:
        request = urllib.request.Request(
            f"{BASE_URL}{path}",
            method="GET",
        )

        with urllib.request.urlopen(request, timeout=HTTP_TIMEOUT) as response:
            body = response.read().decode("utf-8")
            return response.status, body

    except (urllib.error.URLError, TimeoutError, OSError):
        return None, None


def http_post(path, payload):
    """Perform a bounded HTTP POST and return status/body."""
    try:
        data = json.dumps(payload).encode("utf-8")

        request = urllib.request.Request(
            f"{BASE_URL}{path}",
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        with urllib.request.urlopen(request, timeout=HTTP_TIMEOUT) as response:
            body = response.read().decode("utf-8")
            return response.status, body

    except (urllib.error.URLError, TimeoutError, OSError):
        return None, None

def get_app_services():
    """Discover declared app-* services from Compose."""
    result = run_command(["docker", "compose", "config", "--services"])

    if result is None or result.returncode != 0:
        return set()

    return {
        service
        for service in result.stdout.splitlines()
        if service.startswith("app-")
    }

def check_records_write():
    """Verify that records can be written to PostgreSQL."""
    status, body = http_post(
        "/records",
        {"title": "validator-test"},
    )

    if status == 201:
        try:
            payload = json.loads(body)

            if payload.get("record", {}).get("title") == "validator-test":
                pass_check("POST /records writes to PostgreSQL")
                return

        except json.JSONDecodeError:
            pass

    fail_check("POST /records writes to PostgreSQL")

def check_http(path, description):
    """PASS when an endpoint returns a successful HTTP status."""
    status, _ = http_get(path)

    if status is not None and 200 <= status < 300:
        pass_check(description)
        return True

    fail_check(description)
    return False


def check_compose():
    """Validate the Compose configuration."""
    return check_command(
        "Compose configuration is valid",
        ["docker", "compose", "config", "--quiet"],
    )


def check_containers():
    """Check that all required services are running."""
    result = run_command(
        [
            "docker",
            "compose",
            "ps",
            "--status",
            "running",
            "--services",
        ]
    )

    required = {"nginx", "postgres", "redis"} | get_app_services()

    if result is None or result.returncode != 0:
        for service in sorted(required):
            fail_check(f"{service} is running")
        return

    running = set(result.stdout.splitlines())

    for service in sorted(required):
        if service in running:
            pass_check(f"{service} is running")
        else:
            fail_check(f"{service} is running")


def check_postgres():
    """Wait for PostgreSQL readiness."""
    wait_for_command(
        [
            "docker",
            "exec",
            "postgres",
            "pg_isready",
            "-U",
            "barq_app",
            "-d",
            "barq_tasks",
        ],
        "PostgreSQL is ready",
    )

def check_redis():
    """Wait for Redis readiness."""
    wait_for_command(
        ["docker", "exec", "redis", "redis-cli", "ping"],
        "Redis is ready",
    )

def check_instances():
    """Prove that NGINX sends traffic to both application instances."""
    expected = get_app_services()
    seen_instances = set()

    for _ in range(max(20, len(expected) * 10)):
        status, body = http_get("/instance")

        if status is None:
            continue

        try:
            payload = json.loads(body)
        except json.JSONDecodeError:
            continue

        instance_id = payload.get("instance_id")

        if instance_id:
            seen_instances.add(instance_id)

    if expected.issubset(seen_instances):
        pass_check(
            f"Traffic reaches all application instances: "
            f"{sorted(expected)}"
        )
    else:
        fail_check(
            f"Traffic reaches all application instances "
            f"(expected={sorted(expected)}, seen={sorted(seen_instances)})"
        )

def check_network_isolation():
    """Verify NGINX is isolated from the backend network."""
    result = run_command(
        [
            "docker",
            "inspect",
            "nginx",
            "--format",
            "{{range $name, $_ := .NetworkSettings.Networks}}{{$name}} {{end}}",
        ]
    )

    if result is None or result.returncode != 0:
        fail_check("NGINX network configuration can be inspected")
        return

    networks = set(result.stdout.split())

    if not any(network.endswith("_backend") for network in networks):
        pass_check("NGINX is not attached to the backend network")
    else:
        fail_check("NGINX is not attached to the backend network")


def check_host_ports():
    """Ensure only NGINX publishes a host port."""
    result = run_command(
        ["docker", "compose", "ps", "--format", "{{.Name}} {{.Ports}}"]
    )

    if result is None or result.returncode != 0:
        fail_check("Only NGINX publishes a host port")
        return

    violations = []

    for line in result.stdout.splitlines():
        if not line.strip():
            continue

        name, _, ports = line.partition(" ")

        if name != "nginx" and "->" in ports:
            violations.append(name)

    if violations:
        fail_check(
            f"Only NGINX publishes a host port "
            f"(unexpected: {sorted(violations)})"
        )
    else:
        pass_check("Only NGINX publishes a host port")



def main():
    """Run all validation checks."""
    print("=== BARQ Assessment Validation ===")
    print()

    check_compose()
    check_containers()

    check_postgres()
    check_redis()

    check_http("/", "Public HTTP endpoint is reachable")
    check_http("/health", "/health responds successfully")
    check_http("/ready", "/ready reports readiness")
    check_http("/instance", "/instance responds successfully")
    check_http("/records", "GET /records responds successfully")
    check_records_write()
    check_http("/counter", "/counter responds successfully")

    check_instances()
    check_network_isolation()
    check_host_ports()

    print()
    print("=== Validation Summary ===")
    print(f"PASS: {passed}")
    print(f"FAIL: {failed}")

    if failed == 0:
        print("RESULT: PASS")
        return 0

    print("RESULT: FAIL")
    return 1


if __name__ == "__main__":
    sys.exit(main())
