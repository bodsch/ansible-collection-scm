#!/usr/bin/python
# -*- coding: utf-8 -*-

"""
Ansible module to run Forgejo database migrations via the Forgejo CLI.

This module executes `forgejo migrate` against a given Forgejo installation and
reports `changed=True` on successful execution because migrations can modify the
database schema.

Key features:
- Strict input validation (paths, parameters).
- Check mode support (reports what would happen without executing the migration).
- Optional pass-through parameters for `forgejo migrate`.
- Robust error handling without leaking irrelevant logs.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, List, Literal, Sequence, Tuple, TypedDict, cast

from ansible.module_utils.basic import AnsibleModule

DOCUMENTATION = r"""
---
module: forgejo_migrate
author: Bodo 'bodsch' Schulz (@bodsch)
version_added: "1.0.0"

short_description: Run Forgejo database migrations.
description:
  - This module runs the C(forgejo migrate) command to perform a database migration.
  - It must be executed as the Forgejo service user to have access to the working directory and configuration.
  - A successful run indicates a changed state, as the migration may modify the database schema.
  - Supports check mode: reports changes without running the migration.

options:
  command:
    description:
      - The command to execute. Currently only C(migrate) is supported.
    required: false
    type: str
    choices: [migrate]
    default: migrate

  parameters:
    description:
      - Additional command-line parameters passed to C(forgejo migrate).
      - This list is appended verbatim.
    required: false
    type: list
    elements: str
    default: []

  working_dir:
    description:
      - Path to the Forgejo working directory (C(--work-path)).
      - Typically the home directory of the Forgejo service user.
    required: false
    type: str
    default: "/var/lib/forgejo"

  config:
    description:
      - Path to the Forgejo configuration file (C(--config)).
    required: false
    type: str
    default: "/etc/forgejo/forgejo.ini"

notes:
  - The module reports C(changed=true) when the migration is executed successfully.
  - In check mode, it reports C(changed=true) but does not execute the migration.
"""

EXAMPLES = r"""
- name: Migrate Forgejo database
  remote_user: "{{ forgejo_remote_user }}"
  become_user: "{{ forgejo_system_user }}"
  become: true
  bodsch.scm.forgejo_migrate:
    config: "{{ forgejo_config_dir }}/forgejo.ini"
    working_dir: "{{ forgejo_working_dir }}"
    parameters:
      - "--verbose"
"""

RETURN = r"""
changed:
  description: Indicates whether the database migration was executed (or would be executed in check mode).
  returned: always
  type: bool
  sample: true

failed:
  description: Indicates if the module encountered an error.
  returned: always
  type: bool
  sample: false

msg:
  description: Human-readable message about the migration result.
  returned: always
  type: str
  sample: "Database migration executed successfully."

rc:
  description: CLI return code (only returned on failures).
  returned: when failed
  type: int

stdout:
  description: CLI stdout (only returned on failures).
  returned: when failed
  type: str

stderr:
  description: CLI stderr (only returned on failures).
  returned: when failed
  type: str
"""


Command = Literal["migrate"]


class ModuleResult(TypedDict, total=False):
    """Typed return structure for this module."""

    failed: bool
    changed: bool
    msg: str
    rc: int
    stdout: str
    stderr: str


class ForgejoMigrate:
    """
    Execute Forgejo database migration through the Forgejo CLI.

    The class validates inputs, builds the CLI argument list, and runs the
    migration command. Failures are returned in a structured way; hard validation
    errors fail fast via `module.fail_json()`.
    """

    def __init__(self, module: AnsibleModule) -> None:
        """
        Initialize the migrator from Ansible module parameters.

        Args:
            module: The active AnsibleModule instance.
        """
        self.module = module

        self.command: Command = cast(Command, module.params.get("command", "migrate"))
        self.parameters: List[str] = self._as_str_list(
            module.params.get("parameters", [])
        )

        self.working_dir: str = cast(
            str, module.params.get("working_dir", "/var/lib/forgejo")
        )
        self.config: str = cast(
            str, module.params.get("config", "/etc/forgejo/forgejo.ini")
        )

        self.forgejo_bin: str = module.get_bin_path("forgejo", required=True)

    def run(self) -> ModuleResult:
        """
        Run the selected operation.

        Returns:
            ModuleResult compatible with `module.exit_json()`.
        """
        self._validate_inputs()

        os.chdir(self.working_dir)

        if self.command != "migrate":
            self.module.fail_json(
                msg=f"Unsupported command '{self.command}'. Supported: migrate"
            )

        return self.migrate()

    def migrate(self) -> ModuleResult:
        """
        Execute `forgejo migrate`.

        Returns:
            ModuleResult indicating whether the migration ran successfully.
        """
        if self.module.check_mode:
            return {
                "failed": False,
                "changed": True,
                "msg": "Database migration would be executed (check mode).",
            }

        args = self._build_args()

        rc, out, err = self._exec(args)
        if rc == 0:
            return {
                "failed": False,
                "changed": True,
                "msg": "Database migration executed successfully.",
            }

        return {
            "failed": True,
            "changed": False,
            "msg": (err or out or "Database migration failed.").strip(),
            "rc": rc,
            "stdout": (out or "").strip(),
            "stderr": (err or "").strip(),
        }

    def _build_args(self) -> List[str]:
        """
        Build the command line argument list for the Forgejo CLI.

        Returns:
            The full CLI token list.
        """
        args: List[str] = [
            self.forgejo_bin,
            "--work-path",
            self.working_dir,
            "--config",
            self.config,
            "migrate",
        ]
        if self.parameters:
            args += self.parameters
        return args

    def _validate_inputs(self) -> None:
        """
        Validate filesystem paths and parameter types.

        Raises:
            Calls `module.fail_json()` on validation errors.
        """
        wd = Path(self.working_dir)
        if not wd.exists() or not wd.is_dir():
            self.module.fail_json(
                msg=f"working_dir '{self.working_dir}' does not exist or is not a directory."
            )

        cfg = Path(self.config)
        if not cfg.exists() or not cfg.is_file():
            self.module.fail_json(
                msg=f"config '{self.config}' does not exist or is not a file."
            )

        # Ensure parameters is a list of strings (best-effort, but reject dict-like).
        params = self.module.params.get("parameters", [])
        if isinstance(params, dict):
            self.module.fail_json(
                msg="parameters must be a list of strings, not a dict."
            )

    def _exec(self, commands: Sequence[str]) -> Tuple[int, str, str]:
        """
        Execute a command via Ansible's `run_command` without raising on non-zero RC.

        Args:
            commands: Command token list.

        Returns:
            Tuple (rc, stdout, stderr).
        """
        rc, out, err = self.module.run_command(list(commands), check_rc=False)
        return int(rc), cast(str, out), cast(str, err)

    @staticmethod
    def _as_str_list(value: Any) -> List[str]:
        """
        Convert a value into a list of strings.

        Args:
            value: Input value.

        Returns:
            List of strings.
        """
        if value is None:
            return []
        if isinstance(value, list):
            return [str(v) for v in value]
        return [str(value)]


def main() -> None:
    """
    Ansible module entry point.

    Defines arguments and runs the migrator.
    """
    specs: Dict[str, Any] = dict(
        command=dict(type="str", default="migrate", choices=["migrate"]),
        parameters=dict(type="list", elements="str", required=False, default=[]),
        working_dir=dict(type="str", required=False, default="/var/lib/forgejo"),
        config=dict(type="str", required=False, default="/etc/forgejo/forgejo.ini"),
    )

    module = AnsibleModule(
        argument_spec=specs,
        supports_check_mode=True,
    )

    migrator = ForgejoMigrate(module)
    result = migrator.run()
    module.exit_json(**result)


if __name__ == "__main__":
    main()
