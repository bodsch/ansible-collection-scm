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

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional, Sequence, Tuple, TypedDict, cast

from ansible.module_utils.basic import AnsibleModule

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
      - Optional keys: C(scope), C(labels) (list of labels).
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
    secret: str
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
        state: List[RunnerResult] = []
        any_changed = False
        any_failed = False

        for runner_spec, parse_error in self._parse_runner_specs(self.runners_raw):
            if parse_error is not None:
                state.append(parse_error)
                any_failed = True
                continue

            if self.module.check_mode:
                state.append(
                    {
                        "name": runner_spec.name,
                        "changed": True,
                        "failed": False,
                        "msg": f"Runner {runner_spec.name} would be registered (check mode).",
                    }
                )
                any_changed = True
                continue

            rc, out, err = self.register_runner(runner_spec)

            if rc == 0:
                state.append(
                    {
                        "name": runner_spec.name,
                        "changed": True,
                        "failed": False,
                        "msg": f"Runner {runner_spec.name} successfully registered.",
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
                            or f"Runner {runner_spec.name} registration failed."
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

    def _validate_paths(self) -> None:
        """
        Validate required filesystem paths.

        Raises:
            Calls module.fail_json on invalid paths.
        """
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
