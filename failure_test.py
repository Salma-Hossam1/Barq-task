#!/usr/bin/env python3

"""Test backend failure, continued traffic, and backend recovery."""

import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request


# BASE_URL = "http://127.0.0.1:8080"
# APP_TO_FAIL = "app-01"
HTTP_TIMEOUT = 3
NORMAL_REQUESTS = 10
FAILURE_REQUESTS = 20
RECOVERY_ATTEMPTS = 20
RECOVERY_DELAY = 1

def get_base_url():
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

def run_command(command, timeout=10):
    """Run a command with a bounded timeout."""
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

def get_app_services():
    result = run_command(["docker", "compose", "config", "--services"])

    if result is None or result.returncode != 0:
        return []

    return sorted(
        service
        for service in result.stdout.splitlines()
        if service.startswith("app-")
    )

def request_instance():
    """Request /instance and return its status and instance ID."""
    try:
        request = urllib.request.Request(
            f"{BASE_URL}/instance",
            method="GET",
        )

        with urllib.request.urlopen(request, timeout=HTTP_TIMEOUT) as response:
            body = response.read().decode("utf-8")
            payload = json.loads(body)

            return response.status, payload.get("instance_id")

    except (
        urllib.error.URLError,
        TimeoutError,
        OSError,
        json.JSONDecodeError,
    ):
        return None, None


def measure_traffic(requests_count):
    """Send requests and return success count and observed instances."""
    successes = 0
    failures = 0
    instances = set()

    for _ in range(requests_count):
        status, instance_id = request_instance()

        if status is not None and 200 <= status < 300:
            successes += 1

            if instance_id:
                instances.add(instance_id)
        else:
            failures += 1

    return successes, failures, instances


def container_is_healthy(container):
    """Check whether a container reports healthy."""
    result = run_command(
        [
            "docker",
            "inspect",
            "--format",
            "{{.State.Health.Status}}",
            container,
        ]
    )

    return (
        result is not None
        and result.returncode == 0
        and result.stdout.strip() == "healthy"
    )


def start_backend(app_to_fail):
    """Restore the failed backend."""
    result = run_command(
        ["docker", "compose", "start", app_to_fail]
    )

    return result is not None and result.returncode == 0


def stop_backend(app_to_fail):
    """Stop the backend selected for the failure test."""
    result = run_command(
        ["docker", "compose", "stop", app_to_fail]
    )

    return result is not None and result.returncode == 0


def wait_for_recovery(app_to_fail):
    """Wait for the failed backend to become healthy."""
    for _ in range(RECOVERY_ATTEMPTS):
        if container_is_healthy(app_to_fail):
            return True

        time.sleep(RECOVERY_DELAY)

    return False


def main():

    app_services = get_app_services()

    if len(app_services) < 2:
        print("FAIL: at least two application instances are required")
        return 1

    app_to_fail = os.getenv("APP_TO_FAIL", app_services[0])
    surviving_apps = set(app_services) - {app_to_fail}

    if app_to_fail not in app_services:
        print(f"FAIL: {app_to_fail} is not a declared application service")
        return 1


    """Run the failure and recovery test."""
    print("=== BARQ Failure / Recovery Test ===")
    print(f"Base URL: {BASE_URL}")
    print(f"Application instances: {app_services}")
    print(f"Instance selected for failure: {app_to_fail}")
    print()


    print("Measuring normal traffic...")
    normal_successes, normal_failures, normal_instances = measure_traffic(
        NORMAL_REQUESTS
    )

    print(
        f"Normal traffic: {normal_successes}/{NORMAL_REQUESTS} successful; "
        f"instances={sorted(normal_instances)}; "
        f"errors={normal_failures}"
    )

    if not set(app_services).issubset(normal_instances):
        print("FAIL: normal traffic did not reach all application instances")
        return 1

    print()
    print(f"Stopping {app_to_fail}...")

    if not stop_backend(app_to_fail):
        print(f"FAIL: could not stop {app_to_fail}")
        return 1

    try:
        time.sleep(2)

        print(f"Measuring traffic while {app_to_fail} is stopped...")
        failure_successes, failure_failures, failure_instances = measure_traffic(
            FAILURE_REQUESTS
        )

        print(
            f"Failure traffic: {failure_successes}/{FAILURE_REQUESTS} successful; "
            f"instances={sorted(failure_instances)}; "
            f"errors={failure_failures}"
        )

        if not surviving_apps.intersection(failure_instances):
            print("FAIL: healthy application instances did not serve traffic")
            return 1

        if failure_successes == 0:
            print("FAIL: no successful traffic during backend failure")
            return 1

        print()
        print(f"Restoring {app_to_fail}...")

        if not start_backend(app_to_fail):
            print(f"FAIL: could not start {app_to_fail}")
            return 1

        if not wait_for_recovery(app_to_fail):
            print(f"FAIL: {app_to_fail} did not become healthy")
            return 1

        print(f"PASS: {app_to_fail} recovered and is healthy")

        print("Waiting for traffic to reach the recovered instance...")

        for attempt in range(1, RECOVERY_ATTEMPTS + 1):
            _, _, recovery_instances = measure_traffic(5)

            if app_to_fail in recovery_instances:
                print(
                    f"PASS: {app_to_fail} served traffic after recovery "
                    f"(attempt {attempt})"
                )
                print()
                print("RESULT: PASS")
                return 0

            time.sleep(RECOVERY_DELAY)

        print(f"FAIL: {app_to_fail} recovered but did not receive traffic")
        return 1

    finally:
        if not container_is_healthy(app_to_fail):
            print(f"Cleanup: ensuring {app_to_fail} is running...")
            start_backend(app_to_fail)


if __name__ == "__main__":
    sys.exit(main())
