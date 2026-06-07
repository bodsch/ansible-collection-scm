# coding: utf-8
"""
Validate the rendered /etc/forgejo-runner/config.yaml on the instance.

The config is parsed once per test session (cached fixture) and then checked
structurally and semantically. Structural checks ensure required sections and
keys exist with correct types; semantic checks compare values against the
Ansible variables exposed via the `get_vars` fixture, so the test follows
your defaults rather than hard-coded duplicates.
"""

from __future__ import annotations

import re
from typing import Any

import pytest
import yaml

from helper.molecule import get_vars, infra_hosts

testinfra_hosts = infra_hosts(host_name="instance")

CONFIG_PATH = "/etc/forgejo-runner/config.yaml"

# Forgejo runner duration strings: "15s", "2h", "3h30m", "500ms"
_DURATION_RE = re.compile(r"^\d+(ms|s|m|h)(\d+(ms|s|m|h))*$")

# Forgejo runner label format: "<name>:<scheduler>://<image-or-host>"
# Schedulers: docker, host, lxc, k8s, self-hosted
_LABEL_RE = re.compile(
    r"^[A-Za-z0-9._-]+:(docker|host|lxc|k8s|self-hosted)://.+$"
)

# UUID v4 / generic 8-4-4-4-12 hex form
_UUID_RE = re.compile(
    r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-"
    r"[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
)


# --- fixtures --------------------------------------------------------------


@pytest.fixture(scope="module")
def config(host) -> dict[str, Any]:
    """
    Read and parse the runner configuration file once per module.

    :param host: testinfra host fixture
    :returns: parsed YAML document as a dict
    :raises AssertionError: if the file is missing or unparsable
    """
    f = host.file(CONFIG_PATH)
    assert f.exists, f"{CONFIG_PATH} does not exist"
    assert f.is_file, f"{CONFIG_PATH} is not a regular file"

    content = f.content_string
    try:
        parsed = yaml.safe_load(content)
    except yaml.YAMLError as exc:
        pytest.fail(f"{CONFIG_PATH} is not valid YAML: {exc}")

    assert isinstance(parsed, dict), (
        f"{CONFIG_PATH} top-level must be a mapping, got {type(parsed).__name__}"
    )
    return parsed


# --- structural checks -----------------------------------------------------


@pytest.mark.parametrize(
    "section",
    ["log", "runner", "cache", "container", "server"],
)
def test_required_sections_present(config, section):
    """Verify each top-level section exists and is a mapping (or None for `host`)."""
    assert section in config, f"missing top-level section: {section}"
    assert isinstance(config[section], dict), (
        f"section '{section}' must be a mapping, got {type(config[section]).__name__}"
    )


def test_optional_host_section(config):
    """The `host` section is allowed to be empty/null but must be declared."""
    assert "host" in config
    assert config["host"] is None or isinstance(config["host"], dict)


# --- log section -----------------------------------------------------------


def test_log_section(config):
    """Validate logging configuration values."""
    log = config["log"]

    assert log.get("level") in {"trace", "debug", "info", "warn", "error", "fatal"}, (
        f"log.level invalid: {log.get('level')!r}"
    )
    assert log.get("job_level") in {"trace", "debug", "info", "warn", "error", "fatal"}, (
        f"log.job_level invalid: {log.get('job_level')!r}"
    )


# --- runner section --------------------------------------------------------


def test_runner_section_types(config):
    """Validate runner section field types and value ranges."""
    runner = config["runner"]

    assert isinstance(runner.get("capacity"), int) and runner["capacity"] >= 1, (
        f"runner.capacity must be int >= 1, got {runner.get('capacity')!r}"
    )
    assert isinstance(runner.get("insecure"), bool)

    for key in ("timeout", "shutdown_timeout", "fetch_timeout",
                "fetch_interval", "report_interval"):
        value = runner.get(key)
        assert isinstance(value, str), f"runner.{key} must be a string, got {type(value).__name__}"
        assert _DURATION_RE.match(value), (
            f"runner.{key}={value!r} is not a valid Go duration"
        )


def test_runner_labels(config):
    """Validate label list shape and per-entry format."""

    #forgejo_runner_config = get_vars.get("forgejo_runner_config")
    #runner_labels = forgejo_runner_config.get("runner", {}).get("labels", [])

    labels = config["runner"].get("labels")

    if labels:
        assert isinstance(labels, list) and len(labels) >= 1, (
            "runner.labels must be a non-empty list"
        )

        for label in labels:
            assert isinstance(label, str), f"label must be string, got {type(label).__name__}"
            # assert _LABEL_RE.match(label), f"label malformed: {label!r}"


def test_runner_values_match_vars(config, get_vars):
    """
    Compare runner values against Ansible variables when defined.

    Skips silently for variables that are not exposed via get_vars, so the
    test stays useful even if the role's variable names diverge.
    """
    runner = config["runner"]
    mapping = {
        "capacity": "forgejo_runner_capacity",
        "timeout": "forgejo_runner_timeout",
        "shutdown_timeout": "forgejo_runner_shutdown_timeout",
        "insecure": "forgejo_runner_insecure",
    }
    for cfg_key, var_name in mapping.items():
        expected = get_vars.get(var_name)
        if expected is None:
            continue
        assert runner[cfg_key] == expected, (
            f"runner.{cfg_key}={runner[cfg_key]!r} does not match "
            f"{var_name}={expected!r}"
        )


# --- cache section ---------------------------------------------------------


def test_cache_section(config):
    """Validate cache configuration."""
    cache = config["cache"]

    cache_enabled = cache.get("enabled")

    assert isinstance(cache_enabled, bool)

    if cache_enabled:
        assert isinstance(cache.get("dir"), str) and cache["dir"].startswith("/"), (
            "cache.dir must be an absolute path"
        )
        for key in ("port", "proxy_port"):
            assert isinstance(cache.get(key), int) and 0 <= cache[key] <= 65535, (
                f"cache.{key} must be 0..65535, got {cache.get(key)!r}"
            )
        assert isinstance(cache.get("secret"), str) and len(cache["secret"]) > 0, (
            "cache.secret must be a non-empty string"
        )


# --- container section -----------------------------------------------------


def test_container_section(config):
    """Validate container configuration."""
    container = config["container"]

    for key in ("enable_ipv6", "privileged", "force_pull", "force_rebuild"):
        assert isinstance(container.get(key), bool), (
            f"container.{key} must be bool, got {type(container.get(key)).__name__}"
        )

    docker_host = container.get("docker_host")
    assert isinstance(docker_host, str)
    # Accepted forms: "-" (auto), "automount", unix:// path, tcp:// host
    assert (
        docker_host in {"-", "automount"}
        or docker_host.startswith("unix://")
        or docker_host.startswith("tcp://")
    ), f"container.docker_host invalid: {docker_host!r}"


# --- server / connections --------------------------------------------------


def test_server_connections_structure(config):
    """
    Validate the server.connections subtree shape.

    Each connection must be a mapping containing 'url' and 'uuid' plus
    exactly one of 'token' or 'token_url' (mutually exclusive).
    """
    server = config["server"]
    connections = server.get("connections")

    assert isinstance(connections, dict) and len(connections) >= 1, (
        "server.connections must be a non-empty mapping"
    )

    for name, conn in connections.items():
        assert isinstance(name, str) and name, f"connection name invalid: {name!r}"
        assert isinstance(conn, dict), f"connection '{name}' must be a mapping"

        # Required keys
        assert "url" in conn, f"connection '{name}' missing 'url'"
        assert "uuid" in conn, f"connection '{name}' missing 'uuid'"

        # Mutually exclusive: exactly one of token / token_url must be set.
        # Cast to bool explicitly so XOR works regardless of value type.
        has_token = bool(conn.get("token"))
        has_token_url = bool(conn.get("token_url"))
        assert has_token ^ has_token_url, (
            f"connection '{name}' must define exactly one of "
            f"'token' or 'token_url' (got token={has_token}, "
            f"token_url={has_token_url})"
        )


def test_server_connection_values(config):
    """Validate the contents of each connection entry."""
    for name, conn in config["server"]["connections"].items():
        url = conn["url"]
        assert isinstance(url, str) and re.match(r"^https?://", url), (
            f"connection '{name}': url must start with http(s)://"
        )

        uuid_val = conn["uuid"]
        assert isinstance(uuid_val, str) and _UUID_RE.match(uuid_val), (
            f"connection '{name}': uuid {uuid_val!r} is not in 8-4-4-4-12 hex form"
        )

        if "token_url" in conn and conn["token_url"]:
            tu = conn["token_url"]
            assert tu.startswith("file://"), (
                f"connection '{name}': token_url must use file:// scheme, got {tu!r}"
            )

        if "labels" in conn:
            labels = conn["labels"]
            assert isinstance(labels, list) and labels, (
                f"connection '{name}': labels must be a non-empty list when set"
            )
            # for label in labels:
            #     assert _LABEL_RE.match(label), (
            #         f"connection '{name}': label malformed: {label!r}"
            #     )


def test_server_connection_token_file_exists(host, config):
    """
    For each connection using token_url=file://, verify the referenced file
    exists, is owned correctly and contains a 40-char hex token.
    """
    for name, conn in config["server"]["connections"].items():
        token_url = conn.get("token_url")
        if not token_url or not token_url.startswith("file://"):
            continue

        path = token_url[len("file://"):]
        token_file = host.file(path)

        assert token_file.exists, f"token file missing: {path}"
        assert token_file.is_file, f"token path is not a regular file: {path}"

        # Permission hygiene: not world-readable
        mode = token_file.mode & 0o077
        assert mode == 0, (
            f"token file {path} is too permissive (mode={oct(token_file.mode)})"
        )

        content = token_file.content_string.strip()
        assert re.match(r"^[0-9a-f]{40}$", content), (
            f"token file {path} content is not a 40-char hex string"
        )
