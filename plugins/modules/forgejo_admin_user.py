#!/usr/bin/python
# -*- coding: utf-8 -*-

"""
Ansible module to manage a Forgejo admin user.

This module is intended to be executed on the Forgejo host and typically as the
Forgejo service user so the Forgejo CLI can access the configured installation.

Behavior:
- Ensures a single admin user exists (idempotent).
- If the user already exists, no change is reported.
- User deletion is currently not supported (state=absent returns a message).

The module uses the collection utility:
`ansible_collections.bodsch.scm.plugins.module_utils.forgejo.cli_user.ForgejoCliUser`.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Literal, Mapping, Optional, TypedDict, cast

from ansible.module_utils.basic import AnsibleModule
from ansible_collections.bodsch.scm.plugins.module_utils.forgejo.cli_user import (
    ForgejoCliUser,
)

DOCUMENTATION = r"""
---
module: forgejo_admin_user
author: Bodo 'bodsch' Schulz (@bodsch)
version_added: "1.0.0"

short_description: Manage Forgejo admin users.
description:
  - This module creates an admin user in a Forgejo installation if it does not exist.
  - Deletion of users is currently not supported.
  - The module must be executed as the Forgejo service user to access the database.

options:
  state:
    description:
      - Target state of the user.
      - C(present) ensures the user exists.
      - C(absent) is currently not supported and will return without changes.
    required: false
    type: str
    choices: ["present", "absent"]
    default: "present"

  username:
    description:
      - The Forgejo username to create if it does not exist.
    required: false
    type: str

  password:
    description:
      - Password for the Forgejo user.
      - Required when I(state=present) and the user does not yet exist.
    required: false
    type: str
    no_log: true

  email:
    description:
      - Email address of the Forgejo user.
      - Required when I(state=present) and the user does not yet exist.
    required: false
    type: str

  working_dir:
    description:
      - Path to the Forgejo working directory.
      - This is typically the home directory of the Forgejo service user.
    required: false
    type: str
    default: "/var/lib/forgejo"

  config:
    description:
      - Path to the Forgejo configuration file.
    required: false
    type: str
    default: "/etc/forgejo/forgejo.ini"

notes:
  - Only user creation is currently supported.
  - If the user already exists, the module will report no change.
"""

EXAMPLES = r"""
- name: create admin user
  remote_user: "{{ forgejo_remote_user }}"
  become_user: "{{ forgejo_system_user }}"
  become: true
  bodsch.scm.forgejo_admin_user:
    state: present
    username: "{{ forgejo_admin_user.username }}"
    password: "{{ forgejo_admin_user.password }}"
    email: "{{ forgejo_admin_user.email }}"
    config: "{{ forgejo_config_dir }}/forgejo.ini"
    working_dir: "{{ forgejo_working_dir }}"
  when:
    - not ansible_check_mode
    - (forgejo_admin_user.username is defined and forgejo_admin_user.username | string | length > 0)
    - (forgejo_admin_user.password is defined and forgejo_admin_user.password | string | length > 0)
    - (forgejo_admin_user.email is defined and forgejo_admin_user.email | string | length > 0)
"""

RETURN = r"""
changed:
  description: Indicates whether a Forgejo user was created.
  returned: always
  type: bool
  sample: true

msg:
  description: Human-readable message with details about the operation.
  returned: always
  type: str
  sample: "User admin was created."

user:
  description: The username that was evaluated/managed by this module.
  returned: always
  type: str
  sample: "admin"
"""


class ModuleResult(TypedDict, total=False):
    """Typed structure for module return values."""

    changed: bool
    msg: str
    user: str


State = Literal["present", "absent"]


class ForgejoAdminUser(ForgejoCliUser):
    """
    Ensure a Forgejo admin user exists.

    This class provides idempotent user creation by checking existing Forgejo users
    and creating the requested admin user if missing.

    Deletion is intentionally not implemented. If called with state=absent, a
    non-changing result is returned.
    """

    def __init__(self, module: AnsibleModule) -> None:
        """
        Initialize the manager with module parameters.

        Args:
            module: The active AnsibleModule instance providing parameters and helpers.
        """
        self.module: AnsibleModule = module

        self.state: State = cast(State, module.params.get("state", "present"))
        self.username: Optional[str] = module.params.get("username")
        self.password: Optional[str] = module.params.get("password")
        self.email: Optional[str] = module.params.get("email")

        self.working_dir: str = module.params.get("working_dir", "/var/lib/forgejo")
        self.config: str = module.params.get("config", "/etc/forgejo/forgejo.ini")

        super().__init__(
            module, working_dir=self.working_dir, forgejo_config=self.config
        )

    def _validate_paths(self) -> None:
        """
        Validate working directory and configuration file paths.

        Raises:
            Calls module.fail_json on validation errors.
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

    def _ensure_required_params_for_create(self) -> None:
        """
        Ensure required parameters for user creation are present.

        For idempotency we validate them only when we might need to create the user.
        This method is called after the existence check when applicable.

        Raises:
            Calls module.fail_json on missing parameters.
        """
        if not self.username or not str(self.username).strip():
            self.module.fail_json(
                msg="Parameter 'username' must be set for state=present."
            )

        if not self.password or not str(self.password).strip():
            self.module.fail_json(
                msg="Parameter 'password' must be set to create a new user."
            )

        if not self.email or not str(self.email).strip():
            self.module.fail_json(
                msg="Parameter 'email' must be set to create a new user."
            )

    @staticmethod
    def _user_exists(existing_users: Any, username: str) -> bool:
        """
        Determine whether a user exists in the data returned by list_users().

        The underlying helper may return different shapes depending on implementation.
        This method safely supports common patterns (mapping or iterable).

        Args:
            existing_users: Data returned by ForgejoCliUser.list_users().
            username: Username to search for.

        Returns:
            True if the user exists, otherwise False.
        """
        if isinstance(existing_users, Mapping):
            return username in existing_users
        if isinstance(existing_users, (list, tuple, set, frozenset)):
            return username in existing_users
        return False

    def run(self) -> ModuleResult:
        """
        Execute the desired state operation.

        Returns:
            A dict compatible with AnsibleModule.exit_json().
        """
        result: ModuleResult = {"changed": False, "user": self.username or ""}

        if self.state == "absent":
            result["msg"] = "User deletion is currently not supported."
            return result

        # state == "present"
        self._validate_paths()

        os.chdir(self.working_dir)

        if not self.username or not str(self.username).strip():
            self.module.fail_json(
                msg="Parameter 'username' must be set for state=present."
            )

        try:
            os.chdir(self.working_dir)
        except OSError as exc:
            self.module.fail_json(
                msg=f"Failed to change directory to '{self.working_dir}': {exc}"
            )

        try:
            existing_users = self.list_users()
        except Exception as exc:  # pragma: no cover - depends on external CLI utility
            self.module.fail_json(msg=f"Failed to list Forgejo users: {exc}")

        if self._user_exists(existing_users, self.username):
            result["msg"] = f"User {self.username} already exists."
            return result

        # Only now we require password/email, because creation is needed.
        self._ensure_required_params_for_create()

        if self.module.check_mode:
            return {
                "changed": True,
                "msg": f"User {self.username} would be created (check mode).",
                "user": self.username,
            }

        try:
            created = self.add_user(
                username=self.username,
                password=cast(str, self.password),
                email=cast(str, self.email),
                admin_user=True,
            )
        except Exception as exc:  # pragma: no cover - depends on external CLI utility
            self.module.fail_json(
                msg=f"Failed to create Forgejo user '{self.username}': {exc}"
            )

        # Normalize add_user result to include minimum keys expected by this module.
        if isinstance(created, dict):
            normalized: ModuleResult = {
                "user": self.username,
                "changed": bool(created.get("changed", True)),
            }
            normalized["msg"] = str(
                created.get("msg", f"User {self.username} was created.")
            )
            return normalized

        return {
            "changed": True,
            "msg": f"User {self.username} was created.",
            "user": self.username,
        }


def main() -> None:
    """
    Ansible module entrypoint.

    Defines the argument specification, instantiates the manager and exits with the
    resulting data structure.
    """
    argument_spec = dict(
        state=dict(
            type="str", required=False, default="present", choices=["present", "absent"]
        ),
        username=dict(type="str", required=False),
        password=dict(type="str", required=False, no_log=True),
        email=dict(type="str", required=False),
        working_dir=dict(type="str", required=False, default="/var/lib/forgejo"),
        config=dict(type="str", required=False, default="/etc/forgejo/forgejo.ini"),
    )

    module = AnsibleModule(
        argument_spec=argument_spec,
        supports_check_mode=True,
    )

    manager = ForgejoAdminUser(module)
    result = manager.run()
    module.exit_json(**result)


if __name__ == "__main__":
    main()
