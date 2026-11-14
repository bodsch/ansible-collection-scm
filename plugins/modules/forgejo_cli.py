#!/usr/bin/python
# -*- coding: utf-8 -*-

"""
Ansible module to execute Forgejo CLI operations.

Currently supported:
- Register Forgejo Actions runners via `forgejo forgejo-cli actions register`.

The module is designed to be safe and predictable:
- Typed parameter handling and runner validation.
- No logging of secrets.
- Check mode support (reports what would be done without calling the CLI).
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional, Sequence, Tuple, TypedDict, cast

from ansible.module_utils.basic import AnsibleModule
from ansible_collections.bodsch.scm.plugins.module_utils.forgejo.ini import ForgejoIni
from ansible_collections.bodsch.scm.plugins.module_utils.forgejo.runner import (
    DatabaseConfig,
    ForgejoRunner,
    RunnerSnapshot,
)
from ansible_collections.bodsch.scm.plugins.module_utils.forgejo.utils import (
    is_absolute_path,
)

DOCUMENTATION = r"""
---
module: forgejo_cli
author: Bodo 'bodsch' Schulz <bodo@boone-schulz.de>
version_added: "1.0.0"

short_description: Register Forgejo runners using the Forgejo CLI.
description:
  - This module allows registering Forgejo Actions runners on a Forgejo server
    by invoking the Forgejo CLI.
  - It supports assigning runner secrets, scopes and labels.
  - Check mode is supported and will report planned changes without executing them.

options:
  command:
    description:
      - The operation to perform.
      - Currently only runner registration is supported.
    choices: ["register"]
    default: "register"
    type: str

  parameters:
    description:
      - Optional additional CLI parameters to pass through to the Forgejo CLI command.
      - Use with care; parameters are appended verbatim.
    required: false
    type: list
    elements: str
    default: []

  working_dir:
    description:
      - Working directory for Forgejo CLI commands.
      - This is usually the Forgejo data directory.
    required: true
    type: str

  config:
    description:
      - Path to the Forgejo configuration file.
    required: false
    type: str
    default: /etc/forgejo/forgejo.ini

  runners:
    description:
      - List of runners to register.
      - Each runner must contain C(name) and C(secret).
      - "Optional keys: C(scope), C(labels) (list of labels)."
    required: true
    type: list
    elements: dict

notes:
  - True idempotency depends on Forgejo exposing a CLI to list existing runners.
    This module currently treats a successful registration as a change.
"""

EXAMPLES = r"""
- name: Register runners on Forgejo
  become: true
  remote_user: "{{ forgejo_runner_controller.remoteuser }}"
  become_user: "{{ forgejo_runner_controller.username }}"
  delegate_to: "{{ forgejo_runner_controller.hostname }}"
  bodsch.scm.forgejo_cli:
    command: register
    working_dir: "{{ forgejo_working_dir }}"
    config: "{{ forgejo_config_dir }}/forgejo.ini"
    runners:
      - name: runner1
        secret: "SECRET_TOKEN_1"
        scope: "instance"
        labels:
          - linux
          - x86
"""

RETURN = r"""
changed:
  description: Indicates if any runner was successfully registered.
  returned: always
  type: bool

failed:
  description: True if any runner registration failed.
  returned: always
  type: bool

state:
  description: A list of results for each runner processed.
  returned: always
  type: list
  elements: dict
  sample:
    - name: runner1
      changed: true
      failed: false
      msg: "Runner runner1 successfully registered."
    - name: runner2
      changed: false
      failed: true
      msg: "Missing secret."
"""


Command = Literal["register"]
Scope = Literal[
    "instance", "org", "repo"
]  # Forgejo supports more; keep permissive at runtime.


# Runner UUID as printed by `forgejo forgejo-cli actions register`.
# Only a leading boundary is enforced: the CLI prints the UUID without a
# trailing newline, so a log line may directly follow it.
_UUID_RE = re.compile(
    r"(?<![0-9A-Fa-f-])"
    r"[0-9A-Fa-f]{8}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{12}"
)
_UUID_LINE_START_RE = re.compile(r"^\s*(" + _UUID_RE.pattern + r")", re.MULTILINE)


class RunnerResult(TypedDict, total=False):
    """Result structure for a single runner."""

    name: str
    changed: bool
    failed: bool
    msg: str
    rc: int
    stdout: str
    stderr: str


class ModuleResult(TypedDict):
    """Result structure returned by the module."""

    changed: bool
    failed: bool
    state: List[RunnerResult]


@dataclass(frozen=True)
class RunnerSpec:
    """
    Typed representation of a runner registration request.

    Attributes:
        name: Runner name.
        secret: Runner registration secret.
        scope: Optional scope (e.g. instance/org/repo).
        labels: Optional list of labels.
    """

    name: str
    secret: str = field(repr=False)
    scope: Optional[str] = None
    labels: Tuple[str, ...] = ()


class ForgejoCli:
    """
    Execute Forgejo CLI operations for Ansible.

    This class currently supports runner registration. The implementation avoids
    leaking secrets and provides deterministic results per runner.
    """

    def __init__(self, module: AnsibleModule) -> None:
        """
        Initialize the CLI executor from Ansible module parameters.

        Args:
            module: The active AnsibleModule instance.
        """
        self.module = module
        # self.module.log("ForgejoCli::__init__()")

        self.command: Command = cast(Command, module.params.get("command", "register"))
        self.parameters: List[str] = self._as_str_list(
            module.params.get("parameters", [])
        )

        self.working_dir: str = cast(str, module.params.get("working_dir"))
        self.config: str = cast(
            str, module.params.get("config", "/etc/forgejo/forgejo.ini")
        )

        self.runners_raw: List[Dict[str, Any]] = cast(
            List[Dict[str, Any]], module.params.get("runners", [])
        )

        self.forgejo_bin: str = module.get_bin_path("forgejo", required=True)

    def run(self) -> ModuleResult:
        """
        Execute the requested command.

        Returns:
            A module result containing aggregated status and per-runner state.
        """
        self.module.log("ForgejoCli::run()")

        self._validate_paths()

        os.chdir(self.working_dir)

        if self.command != "register":
            self.module.fail_json(
                msg=f"Unsupported command '{self.command}'. Supported: register"
            )

        return self.register()

    def register(self) -> ModuleResult:
        """
        Register one or more Forgejo Actions runners.

        The underlying CLI call used:
        `forgejo forgejo-cli actions register --name <name> --secret <secret> ...`

        Returns:
            Aggregated module result with one state entry per runner.
        """
        self.module.log("ForgejoCli::register()")

        state: List[RunnerResult] = []
        any_changed = False
        any_failed = False

        created_runners = self.list_runners()

        self.module.log(f"  - created_runners: {created_runners}")

        for runner_spec, parse_error in self._parse_runner_specs(self.runners_raw):
            """ """
            if parse_error is not None:
                state.append(parse_error)
                any_failed = True
                continue

            runner_exists = [
                k for k, _ in created_runners.items() if k == runner_spec.name
            ]

            if len(runner_exists) > 0:
                _uuid = {
                    "uuid": v.get("uuid")
                    for k, v in created_runners.items()
                    if k == runner_spec.name
                }

                state.append(
                    {
                        "name": runner_spec.name,
                        "changed": False,
                        "failed": False,
                        "msg": f"Runner '{runner_spec.name}' already registered.",
                        "uuid": _uuid.get("uuid"),
                    }
                )
                continue

            if self.module.check_mode:
                state.append(
                    {
                        "name": runner_spec.name,
                        "changed": True,
                        "failed": False,
                        "msg": f"Runner '{runner_spec.name}' would be registered (check mode).",
                    }
                )
                any_changed = True
                continue

            rc, out, err = self.register_runner(runner_spec)

            # With debug logging or LOG_SQL enabled, Forgejo writes its log output
            # to stdout as well, interleaved with the runner UUID. The UUID
            # therefore has to be extracted from the mixed output.
            token = self._extract_runner_uuid(out) if rc == 0 else None

            if rc == 0 and token is None:
                state.append(
                    {
                        "name": runner_spec.name,
                        "changed": True,
                        "failed": True,
                        "msg": (
                            f"Runner '{runner_spec.name}' was registered, but no unique "
                            "runner UUID could be found in the CLI output."
                        ),
                        "rc": rc,
                        "stdout": (out or "").strip(),
                        "stderr": (err or "").strip(),
                    }
                )
                any_changed = True
                any_failed = True
            elif rc == 0:
                state.append(
                    {
                        "name": runner_spec.name,
                        "changed": True,
                        "failed": False,
                        "msg": f"Runner '{runner_spec.name}' successfully registered.",
                        "uuid": token,
                    }
                )
                any_changed = True
            else:
                state.append(
                    {
                        "name": runner_spec.name,
                        "changed": False,
                        "failed": True,
                        "msg": (
                            err
                            or out
                            or f"Runner '{runner_spec.name}' registration failed."
                        ).strip(),
                        "rc": rc,
                        "stdout": (out or "").strip(),
                        "stderr": (err or "").strip(),
                    }
                )
                any_failed = True

        return {"changed": any_changed, "failed": any_failed, "state": state}

    def register_runner(self, runner: RunnerSpec) -> Tuple[int, str, str]:
        """
        Register a single runner via Forgejo CLI.

        Args:
            runner: Parsed runner specification.

        Returns:
            Tuple of (rc, stdout, stderr).
        """
        self.module.log(f"ForgejoCli::register_runner(runner: {runner})")

        args: List[str] = [
            self.forgejo_bin,
            "--work-path",
            self.working_dir,
            "--config",
            self.config,
            "forgejo-cli",
            "actions",
            "register",
            "--name",
            runner.name,
            "--secret",
            runner.secret,
        ]

        if runner.scope:
            args += ["--scope", runner.scope]

        if runner.labels:
            args += ["--labels", ",".join(runner.labels)]

        if self.parameters:
            args += self.parameters

        return self._exec(args)

    @staticmethod
    def _extract_runner_uuid(out: Optional[str]) -> Optional[str]:
        """
        Extract the runner UUID from `actions register` stdout.

        stdout may contain Forgejo log lines (debug / LOG_SQL), which can carry
        further UUIDs. Resolution order:
        1. The last UUID at the start of a line (log lines start with a timestamp).
        2. Otherwise the UUID, if exactly one distinct UUID occurs in the output.

        Args:
            out: Raw stdout of the CLI call.

        Returns:
            The runner UUID (lowercase), or None if none or several candidates exist.
        """
        if not out:
            return None

        line_start = _UUID_LINE_START_RE.findall(out)
        if line_start:
            return line_start[-1].lower()

        candidates = {m.lower() for m in _UUID_RE.findall(out)}
        if len(candidates) == 1:
            return candidates.pop()

        return None

    # -----
    def list_runners(self):
        """ """
        self.module.log("ForgejoCli::list_runners()")

        _config = ForgejoIni(self.module, path=self.config)

        _forgejo_config = _config.sections_as_json(
            sections=["database", "__default__"], include_default=True
        )

        if not _forgejo_config:
            """ """
            return {}

        db_path: str | None = None
        db_host: str | None = None
        db_port: int | None = None
        db_name: str | None = None
        db_user: str | None = None
        db_pass: str | None = None
        db_charset: str | None = None
        db_schema: str | None = None
        db_ssl_mode: str | None = None

        db_type = _forgejo_config.get("database", {}).get("DB_TYPE", None)

        if db_type == "sqlite3":
            work_path = _forgejo_config.get("__default__", {}).get(
                "WORK_PATH", "/var/lib/forgejo"
            )
            db_path = _forgejo_config.get("database", {}).get("PATH", "data/forgejo.db")

            if not is_absolute_path(db_path):
                db_path = os.path.join(work_path, db_path)

        elif db_type in ["mariadb", "mysql", "postgres"]:
            """ """
            db_hostname = _forgejo_config.get("database", {}).get("HOST", None)

            if db_hostname and ":" in db_hostname:
                db_host = db_hostname.split(":")[0]
                db_port = int(db_hostname.split(":")[1])
            else:
                db_host = db_hostname
                db_port = 5432 if db_type == "postgres" else 3306

            db_name = _forgejo_config.get("database", {}).get("NAME", None)
            db_user = _forgejo_config.get("database", {}).get("USER", None)
            db_pass = _forgejo_config.get("database", {}).get("PASSWD", None)
            db_charset = "utf8mb4"
            db_schema = _forgejo_config.get("database", {}).get("SCHEMA", None)
            db_ssl_mode = _forgejo_config.get("database", {}).get("SSL_MODE", None)

        config = DatabaseConfig(
            db_type=db_type,
            # SQLite
            sqlite_path=db_path if db_path else "",
            # # MariaDB
            host=(
                db_host if (db_type in ["mariadb", "mysql", "postgres"] and db_host) else ""
            ),  # MariaDB host.
            port=(
                db_port if (db_type in ["mariadb", "mysql", "postgres"] and db_port) else ""
            ),  # MariaDB port.
            user=(
                db_user if (db_type in ["mariadb", "mysql", "postgres"] and db_user) else ""
            ),  # MariaDB username.
            password=(
                db_pass if (db_type in ["mariadb", "mysql", "postgres"] and db_pass) else ""
            ),  # MariaDB password.
            database=(
                db_name if (db_type in ["mariadb", "mysql", "postgres"] and db_name) else ""
            ),  # MariaDB database name.
            charset=(
                db_charset if (db_type in ["mariadb", "mysql", "postgres"] and db_charset) else ""
            ),  # Connection charset (default: utf8mb4).
            # PostgreSQL
            schema=db_schema if (db_type == "postgres" and db_schema) else None,
            ssl_mode=db_ssl_mode if (db_type == "postgres" and db_ssl_mode) else None,
        )

        _runner = ForgejoRunner(self.module)

        _runner_infos: RunnerSnapshot = _runner.get_runner_snapshot(
            db=config, mask_token_salt=False
        )

        self.module.log("  - _runner_infos: {_runner_infos}")

        if _runner_infos.runners:
            return _runner_infos.runners
        else:
            return {}

    def _validate_paths(self) -> None:
        """
        Validate required filesystem paths.

        Raises:
            Calls module.fail_json on invalid paths.
        """
        self.module.log("ForgejoCli::_validate_paths()")

        wd = Path(self.working_dir)
        if not wd.exists() or not wd.is_dir():
            self.module.fail_json(msg=f"missing directory '{self.working_dir}'")

        cfg = Path(self.config)
        if not cfg.exists() or not cfg.is_file():
            self.module.fail_json(msg=f"missing config file '{self.config}'")

    def _parse_runner_specs(
        self, raw_runners: Sequence[Dict[str, Any]]
    ) -> List[Tuple[Optional[RunnerSpec], Optional[RunnerResult]]]:
        """
        Parse and validate runner dictionaries to typed RunnerSpec objects.

        Args:
            raw_runners: Runner dictionaries from module parameters.

        Returns:
            List of tuples: (RunnerSpec or None, RunnerResult error or None).
        """
        self.module.log(f"ForgejoCli::_parse_runner_specs(raw_runners: {raw_runners})")

        parsed: List[Tuple[Optional[RunnerSpec], Optional[RunnerResult]]] = []

        for idx, r in enumerate(raw_runners):
            name = (r.get("name") or "").strip()
            secret = (r.get("secret") or "").strip()
            scope = r.get("scope")
            labels_raw = r.get("labels", [])

            if not name:
                parsed.append(
                    (
                        None,
                        {
                            "name": f"<runner[{idx}]>",
                            "changed": False,
                            "failed": True,
                            "msg": "Missing runner name.",
                        },
                    )
                )
                continue

            if not secret:
                parsed.append(
                    (
                        None,
                        {
                            "name": name,
                            "changed": False,
                            "failed": True,
                            "msg": "Missing secret.",
                        },
                    )
                )
                continue
            else:
                # the secret must be exactly 40 characters long
                if len(secret) < 40:
                    parsed.append(
                        (
                            None,
                            {
                                "name": name,
                                "changed": False,
                                "failed": True,
                                "msg": f"the secret must be exactly 40 characters long, not {len(secret)}.",
                            },
                        )
                    )
                    continue
                else:
                    # the secret must be an hexadecimal string:
                    pass

            labels = self._as_str_tuple(labels_raw)
            if labels is None:
                parsed.append(
                    (
                        None,
                        {
                            "name": name,
                            "changed": False,
                            "failed": True,
                            "msg": "labels must be a list of strings.",
                        },
                    )
                )
                continue

            parsed.append(
                (
                    RunnerSpec(
                        name=name,
                        secret=secret,
                        scope=cast(Optional[str], scope),
                        labels=labels,
                    ),
                    None,
                )
            )

        return parsed

    def _exec(self, args: List[str]) -> Tuple[int, str, str]:
        """
        Execute a CLI command without logging secrets.

        Args:
            args: CLI token list.

        Returns:
            Tuple of (rc, stdout, stderr).
        """
        # self.module.log(f"ForgejoCli::_exec(args: {args})")

        # Never log secrets: redact before any debug output.
        redacted = self._redact_args(args)
        self.module.log(msg=f"cmd: {redacted}")

        rc, out, err = self.module.run_command(args, check_rc=False)
        return int(rc), cast(str, out), cast(str, err)

    @staticmethod
    def _redact_args(args: Sequence[str]) -> List[str]:
        """
        Redact secret values from an argument list.

        Args:
            args: Command arguments.

        Returns:
            A copy of args where the value following '--secret' is replaced by '***'.
        """
        redacted = list(args)
        for i in range(len(redacted) - 1):
            if redacted[i] == "--secret":
                redacted[i + 1] = "***"
        return redacted

    @staticmethod
    def _as_str_list(value: Any) -> List[str]:
        """
        Convert a value to a list of strings.

        Args:
            value: Input value.

        Returns:
            List of strings (best-effort).
        """
        if value is None:
            return []
        if isinstance(value, list):
            return [str(v) for v in value]
        return [str(value)]

    @staticmethod
    def _as_str_tuple(value: Any) -> Optional[Tuple[str, ...]]:
        """
        Convert a value to a tuple of strings, or return None if invalid.

        Args:
            value: Expected to be a list/tuple of values.

        Returns:
            Tuple of strings if valid, otherwise None.
        """
        if value is None:
            return tuple()
        if isinstance(value, (list, tuple)):
            return tuple(str(v) for v in value)
        return None


def main() -> None:
    """
    Ansible module entry point.

    Defines argument specification and executes the Forgejo CLI wrapper.
    """
    specs: Dict[str, Any] = dict(
        command=dict(type="str", default="register", choices=["register"]),
        parameters=dict(type="list", elements="str", required=False, default=[]),
        working_dir=dict(type="str", required=True),
        config=dict(type="str", required=False, default="/etc/forgejo/forgejo.ini"),
        runners=dict(type="list", required=True, elements="dict"),
    )

    module = AnsibleModule(
        argument_spec=specs,
        supports_check_mode=True,
    )

    manager = ForgejoCli(module)
    result = manager.run()

    module.exit_json(**result)


if __name__ == "__main__":
    main()
