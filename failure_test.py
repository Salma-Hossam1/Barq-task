#!/usr/bin/env python3

"""Test backend failure, continued traffic, and backend recovery."""

import json
import subprocess
import sys
import time
import urllib.error
import urllib.request


BASE_URL = "http://127.0.0.1:8080"
APP_TO_FAIL = "app-01"
HTTP_TIMEOUT = 3
NORMAL_REQUESTS = 10
FAILURE_REQUESTS = 20
RECOVERY_ATTEMPTS = 20
RECOVERY_DELAY = 1


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


def start_backend():
    """Restore the failed backend."""
    result = run_command(
        ["docker", "compose", "start", APP_TO_FAIL]
    )

    return result is not None and result.returncode == 0


def stop_backend():
    """Stop the backend selected for the failure test."""
    result = run_command(
        ["docker", "compose", "stop", APP_TO_FAIL]
    )

    return result is not None and result.returncode == 0


def wait_for_recovery():
    """Wait for the failed backend to become healthy."""
    for _ in range(RECOVERY_ATTEMPTS):
        if container_is_healthy(APP_TO_FAIL):
            return True

        time.sleep(RECOVERY_DELAY)

    return False


def main():
    """Run the failure and recovery test."""
    print("=== BARQ Failure / Recovery Test ===")
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

    if "app-01" not in normal_instances or "app-02" not in normal_instances:
        print("FAIL: normal traffic did not reach both application instances")
        return 1

    print()
    print(f"Stopping {APP_TO_FAIL}...")

    if not stop_backend():
        print(f"FAIL: could not stop {APP_TO_FAIL}")
        return 1

    try:
        time.sleep(2)

        print("Measuring traffic while app-01 is stopped...")
        failure_successes, failure_failures, failure_instances = measure_traffic(
            FAILURE_REQUESTS
        )

        print(
            f"Failure traffic: {failure_successes}/{FAILURE_REQUESTS} successful; "
            f"instances={sorted(failure_instances)}; "
            f"errors={failure_failures}"
        )

        if "app-02" not in failure_instances:
            print("FAIL: healthy app-02 did not serve traffic")
            return 1

        if failure_successes == 0:
            print("FAIL: no successful traffic during backend failure")
            return 1

        print()
        print(f"Restoring {APP_TO_FAIL}...")

        if not start_backend():
            print(f"FAIL: could not start {APP_TO_FAIL}")
            return 1

        if not wait_for_recovery():
            print(f"FAIL: {APP_TO_FAIL} did not become healthy")
            return 1

        print(f"PASS: {APP_TO_FAIL} recovered and is healthy")

        print("Waiting for traffic to reach the recovered instance...")

        for attempt in range(1, RECOVERY_ATTEMPTS + 1):
            _, _, recovery_instances = measure_traffic(5)

            if APP_TO_FAIL in recovery_instances:
                print(
                    f"PASS: {APP_TO_FAIL} served traffic after recovery "
                    f"(attempt {attempt})"
                )
                print()
                print("RESULT: PASS")
                return 0

            time.sleep(RECOVERY_DELAY)

        print(f"FAIL: {APP_TO_FAIL} recovered but did not receive traffic")
        return 1

    finally:
        if not container_is_healthy(APP_TO_FAIL):
            print(f"Cleanup: ensuring {APP_TO_FAIL} is running...")
            start_backend()


if __name__ == "__main__":
    sys.exit(main())
