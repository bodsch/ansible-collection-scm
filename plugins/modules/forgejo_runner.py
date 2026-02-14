#!/usr/bin/python3
# -*- coding: utf-8 -*-

"""
Ansible module to create a Forgejo Runner registration file via `forgejo-runner`.

This module is intended to run on the machine where the Forgejo runner is installed.
It performs "offline registration" by generating a `.runner` file using the shared
registration secret and the Forgejo instance URL.

Key features:
- Validates inputs (paths, runner selection, secret format).
- Does not log secrets.
- Supports check mode.
- Provides idempotency by storing a checksum of the desired configuration (with a
  hash of the secret) in a cache directory and re-running the CLI only when needed.

Note:
- `forgejo-runner create-runner-file` creates a `.runner` JSON file in the current
  directory. This module runs the command in `working_dir`.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import socket
from dataclasses import dataclass
from pathlib import Path
from typing import (
    Any,
    Dict,
    List,
    Literal,
    Mapping,
    Optional,
    Sequence,
    Tuple,
    TypedDict,
    cast,
)

from ansible.module_utils.basic import AnsibleModule

DOCUMENTATION = r"""
---
module: forgejo_runner
author: Bodo 'bodsch' Schulz (@bodsch)
version_added: "1.0.0"

short_description: Create a Forgejo runner registration file using forgejo-runner.
description:
  - This module creates a runner registration file (default C(.runner)) using
    the C(forgejo-runner create-runner-file) command.
  - It selects the runner definition matching the current host name (or an
    explicit I(runner_name)).
  - It is designed for Infrastructure-as-Code "offline registration":
    you generate a shared secret, register it on the Forgejo server side, and
    create the runner file on the runner host.

options:
  command:
    description:
      - The operation to perform.
    required: false
    type: str
    choices: ["create_runner"]
    default: "create_runner"

  working_dir:
    description:
      - Directory in which the runner registration file is created.
      - Must exist on the remote host.
    required: true
    type: str

  runners:
    description:
      - List of known runners.
      - Each item must contain C(name), C(secret) and C(instance).
      - C(name) is matched against the host name or I(runner_name).
    required: true
    type: list
    elements: dict

  runner_name:
    description:
      - Optional override for selecting the matching runner entry.
      - If omitted, the module uses the current host name (short and FQDN forms).
    required: false
    type: str

  runner_file:
    description:
      - Name of the runner file created in I(working_dir).
    required: false
    type: str
    default: ".runner"

  cache_dir:
    description:
      - Directory used to store checksum state for idempotency.
      - If omitted, defaults to C(<working_dir>/.ansible/forgejo-runner).
    required: false
    type: str

  use_name_flag:
    description:
      - Try passing C(--name <runner_name>) to the CLI.
      - If the installed forgejo-runner does not support this flag, the module
        automatically retries without it.
    required: false
    type: bool
    default: true

notes:
  - The shared secret must be a 40-character hex string.
  - The module never logs secrets and does not return them.
  - Supports check mode: reports changes without writing files.
"""

EXAMPLES = r"""
- name: Create runner file for this host
  become_user: forgejo-runner
  become: true
  bodsch.scm.forgejo_runner:
    command: create_runner
    working_dir: "/var/lib/forgejo-runner"
    runners:
      - name: "runner01"
        secret: "7c31591e8b67225a116d4a4519ea8e507e08f71f"
        instance: "https://forgejo.example.com"

- name: Create runner file using explicit runner_name override
  bodsch.scm.forgejo_runner:
    working_dir: "/var/lib/forgejo-runner"
    runner_name: "runner01"
    runners: "{{ forgejo_runner_register }}"
"""

RETURN = r"""
changed:
  description: Indicates whether the runner file was created or updated.
  returned: always
  type: bool

failed:
  description: Indicates whether the module failed.
  returned: always
  type: bool

msg:
  description: Human-readable message about the result.
  returned: always
  type: str

runner:
  description: Selected runner name.
  returned: always
  type: str

runner_file:
  description: The runner file path in which the registration data is stored.
  returned: always
  type: str
"""


Command = Literal["create_runner"]


class ModuleResult(TypedDict, total=False):
    """Typed return structure for this module."""

    changed: bool
    failed: bool
    msg: str
    runner: str
    runner_file: str
    rc: int
    stdout: str
    stderr: str


@dataclass(frozen=True)
class RunnerEntry:
    """
    Typed runner entry as provided by `runners`.

    Attributes:
        name: Runner name used for selection.
        secret: Shared offline registration secret (40 hex chars).
        instance: Forgejo base URL (e.g. https://forgejo.example.com).
    """

    name: str
    secret: str
    instance: str


class ForgejoRunner:
    """
    Create and manage a Forgejo runner registration file in an idempotent manner.

    The module selects a runner entry by host name (or explicit override) and
    calls `forgejo-runner create-runner-file`. To avoid unnecessary changes, it
    stores a checksum of the desired configuration (including a hash of the
    secret) in a cache directory.
    """

    _SECRET_RE = re.compile(r"^[0-9a-f]{40}$", re.IGNORECASE)

    def __init__(self, module: AnsibleModule) -> None:
        """
        Initialize from module parameters.

        Args:
            module: The active AnsibleModule instance.
        """
        self.module = module

        self.command: Command = cast(
            Command, module.params.get("command", "create_runner")
        )
        self.working_dir: str = cast(str, module.params.get("working_dir"))
        self.runner_file_name: str = cast(
            str, module.params.get("runner_file", ".runner")
        )
        self.runner_name_override: Optional[str] = module.params.get("runner_name")
        self.use_name_flag: bool = bool(module.params.get("use_name_flag", True))

        runners_raw: List[Dict[str, Any]] = cast(
            List[Dict[str, Any]], module.params.get("runners", [])
        )
        self.runners: List[RunnerEntry] = self._parse_runners(runners_raw)

        cache_dir_param: Optional[str] = module.params.get("cache_dir")
        self.cache_dir: str = cache_dir_param or os.path.join(
            self.working_dir, ".ansible", "forgejo-runner"
        )
        self.checksum_file: Path = Path(self.cache_dir) / "runner.sha256"

        self.forgejo_runner_bin: str = module.get_bin_path(
            "forgejo-runner", required=True
        )

    def run(self) -> ModuleResult:
        """
        Execute the requested command.

        Returns:
            ModuleResult compatible with `module.exit_json()`.
        """
        self._validate_inputs()

        os.chdir(self.working_dir)

        if self.command != "create_runner":
            self.module.fail_json(
                msg=f"Unsupported command '{self.command}'. Supported: create_runner"
            )

        selected_name = self._select_runner_name()
        entry = self._find_runner_entry(selected_name)

        runner_file_path = Path(self.working_dir) / self.runner_file_name

        desired_checksum = self._desired_checksum(
            entry=entry, runner_name=selected_name, runner_file=runner_file_path
        )
        current_checksum = self._read_checksum()

        base_result: ModuleResult = {
            "failed": False,
            "changed": False,
            "runner": selected_name,
            "runner_file": str(runner_file_path),
        }

        if current_checksum == desired_checksum and runner_file_path.exists():
            base_result["msg"] = "Runner file is up-to-date."
            return base_result

        if self.module.check_mode:
            base_result["changed"] = True
            base_result["msg"] = "Runner file would be created/updated (check mode)."
            return base_result

        rc, out, err = self._create_runner_file(
            entry=entry, runner_name=selected_name, runner_file=runner_file_path
        )
        if rc != 0:
            return {
                **base_result,
                "failed": True,
                "changed": False,
                "msg": (err or out or "Runner file creation failed.").strip(),
                "rc": rc,
                "stdout": (out or "").strip(),
                "stderr": (err or "").strip(),
            }

        # Persist checksum only on success.
        self._write_checksum(desired_checksum)

        return {
            **base_result,
            "failed": False,
            "changed": True,
            "msg": f"Runner file '{runner_file_path}' created/updated successfully.",
        }

    # ---------- validation & parsing ----------

    def _validate_inputs(self) -> None:
        """
        Validate filesystem paths and basic parameter correctness.

        Raises:
            module.fail_json on validation errors.
        """
        wd = Path(self.working_dir)
        if not wd.exists() or not wd.is_dir():
            self.module.fail_json(
                msg=f"working_dir '{self.working_dir}' does not exist or is not a directory."
            )

        if not self.runners:
            self.module.fail_json(msg="runners must contain at least one entry.")

        # Ensure cache dir is creatable (but do not create it in check mode).
        cache_parent = Path(self.cache_dir).parent
        if not cache_parent.exists():
            # If the parent directory doesn't exist, fail early (predictable behavior).
            self.module.fail_json(
                msg=f"cache_dir parent '{cache_parent}' does not exist."
            )

    @classmethod
    def _parse_runners(cls, raw: Sequence[Mapping[str, Any]]) -> List[RunnerEntry]:
        """
        Parse and validate the `runners` list into typed RunnerEntry objects.

        Args:
            raw: Runner list from Ansible parameters.

        Returns:
            List of RunnerEntry objects.
        """
        parsed: List[RunnerEntry] = []
        for idx, item in enumerate(raw):
            name = str(item.get("name") or "").strip()
            secret = str(item.get("secret") or "").strip()
            instance = str(item.get("instance") or "").strip()

            if not name:
                raise ValueError(f"runners[{idx}].name is required")
            if not secret:
                raise ValueError(f"runners[{idx}].secret is required")
            if not instance:
                raise ValueError(f"runners[{idx}].instance is required")
            if not cls._SECRET_RE.match(secret):
                raise ValueError(
                    f"runners[{idx}].secret must be a 40-character hex string"
                )

            parsed.append(RunnerEntry(name=name, secret=secret, instance=instance))
        return parsed

    def _select_runner_name(self) -> str:
        """
        Determine the runner name to match against the `runners` list.

        Returns:
            Runner selection name.
        """
        if self.runner_name_override and self.runner_name_override.strip():
            return self.runner_name_override.strip()

        # Prefer a stable selection set (short hostname + fqdn).
        short = socket.gethostname().strip()
        fqdn = socket.getfqdn().strip()

        # If fqdn differs, we still primarily use short, but allow matching via either.
        return short or fqdn

    def _find_runner_entry(self, selected_name: str) -> RunnerEntry:
        """
        Find the runner entry matching this host.

        Matching rules:
        - Exact match against `selected_name`
        - If `runner_name_override` is not set, also match short hostname and FQDN.

        Args:
            selected_name: Candidate name to match.

        Returns:
            Matching RunnerEntry.

        Raises:
            module.fail_json if no match is found.
        """
        candidates: List[str] = [selected_name]
        if not (self.runner_name_override and self.runner_name_override.strip()):
            short = socket.gethostname().strip()
            fqdn = socket.getfqdn().strip()
            for v in (short, fqdn):
                if v and v not in candidates:
                    candidates.append(v)

        for c in candidates:
            for r in self.runners:
                if r.name == c:
                    return r

        known = ", ".join(sorted({r.name for r in self.runners}))
        self.module.fail_json(
            msg=(
                f"Cannot find runner entry for this host. Tried: {candidates}. "
                f"Known runners: {known}"
            )
        )
        raise RuntimeError("unreachable")

    # ---------- idempotency (checksum) ----------

    def _desired_checksum(
        self, entry: RunnerEntry, runner_name: str, runner_file: Path
    ) -> str:
        """
        Compute the desired checksum for idempotency.

        The secret is included only as a SHA-256 hash to avoid persisting secrets.

        Args:
            entry: Selected runner entry.
            runner_name: Effective runner name.
            runner_file: Target runner file path.

        Returns:
            Hex-encoded SHA-256 checksum.
        """
        payload = {
            "runner_name": runner_name,
            "instance": entry.instance,
            "runner_file": str(runner_file),
            "secret_sha256": hashlib.sha256(entry.secret.encode("utf-8")).hexdigest(),
        }
        serialized = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode(
            "utf-8"
        )
        return hashlib.sha256(serialized).hexdigest()

    def _read_checksum(self) -> Optional[str]:
        """
        Read stored checksum from cache, if present.

        Returns:
            Stored checksum string or None.
        """
        try:
            if self.checksum_file.exists():
                return self.checksum_file.read_text(encoding="utf-8").strip() or None
        except OSError:
            return None
        return None

    def _write_checksum(self, value: str) -> None:
        """
        Persist checksum to cache directory.

        Args:
            value: Checksum string.
        """
        cache_path = Path(self.cache_dir)
        cache_path.mkdir(parents=True, exist_ok=True)
        self.checksum_file.write_text(value.strip() + "\n", encoding="utf-8")

    # ---------- CLI execution ----------

    def _create_runner_file(
        self, entry: RunnerEntry, runner_name: str, runner_file: Path
    ) -> Tuple[int, str, str]:
        """
        Run `forgejo-runner create-runner-file` to create/update the runner file.

        The command is executed in `working_dir`, where forgejo-runner will create
        `.runner` by default.

        Args:
            entry: Selected runner configuration.
            runner_name: Effective runner name.
            runner_file: Expected runner file path (used for post-check only).

        Returns:
            Tuple of (rc, stdout, stderr).
        """
        try:
            os.chdir(self.working_dir)
        except OSError as exc:
            return 1, "", f"Failed to change directory to '{self.working_dir}': {exc}"

        base_args: List[str] = [
            self.forgejo_runner_bin,
            "create-runner-file",
            "--instance",
            entry.instance,
            "--secret",
            entry.secret,
        ]

        # Try with --name for compatibility with prior behavior; fallback if unsupported.
        if self.use_name_flag:
            args_with_name = base_args + ["--name", runner_name]
            rc, out, err = self._exec(args_with_name, redact_secret=True)
            if rc == 0:
                return rc, out, err
            # If the flag is unsupported, retry without it.
            if self._looks_like_unknown_flag(err or out):
                return self._exec(base_args, redact_secret=True)
            return rc, out, err

        return self._exec(base_args, redact_secret=True)

    @staticmethod
    def _looks_like_unknown_flag(output: str) -> bool:
        """
        Heuristic to detect "unknown flag" errors from Go-style CLIs.

        Args:
            output: stderr or stdout text.

        Returns:
            True if output suggests an unknown flag, else False.
        """
        text = (output or "").lower()
        return "unknown flag" in text or "flag provided but not defined" in text

    def _exec(
        self, args: Sequence[str], *, redact_secret: bool
    ) -> Tuple[int, str, str]:
        """
        Execute a command with `run_command` and optional secret redaction for logs.

        Args:
            args: CLI token list.
            redact_secret: If True, redact value after '--secret' in log output.

        Returns:
            Tuple (rc, stdout, stderr).
        """
        log_args = list(args)
        if redact_secret:
            for i in range(len(log_args) - 1):
                if log_args[i] == "--secret":
                    log_args[i + 1] = "***"
        self.module.log(msg=f"cmd: {log_args}")

        rc, out, err = self.module.run_command(list(args), check_rc=False)
        return int(rc), cast(str, out), cast(str, err)


def main() -> None:
    """
    Ansible module entry point.

    Defines module arguments and runs the ForgejoRunner manager.
    """
    specs: Dict[str, Any] = dict(
        command=dict(type="str", default="create_runner", choices=["create_runner"]),
        working_dir=dict(type="str", required=True),
        runners=dict(type="list", required=True, elements="dict"),
        runner_name=dict(type="str", required=False),
        runner_file=dict(type="str", required=False, default=".runner"),
        cache_dir=dict(type="str", required=False),
        use_name_flag=dict(type="bool", required=False, default=True),
    )

    module = AnsibleModule(
        argument_spec=specs,
        supports_check_mode=True,
    )

    try:
        manager = ForgejoRunner(module)
    except ValueError as exc:
        module.fail_json(msg=str(exc))

    result = manager.run()
    module.exit_json(**result)


if __name__ == "__main__":
    main()
