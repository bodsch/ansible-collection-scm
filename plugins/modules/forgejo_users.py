#!/usr/bin/python
# -*- coding: utf-8 -*-

"""
Ansible module to manage Forgejo users via the Forgejo REST API.

This module supports:
- Listing existing users (when `users` is empty).
- Creating users (state=present).
- Deleting users (state=absent).

Design goals:
- Predictable, per-user results.
- Check mode support (reports intended changes without performing API calls that modify state).
- No leaking of secrets in logs or return values.
"""

from __future__ import annotations

from typing import (
    Any,
    Dict,
    List,
    Literal,
    Mapping,
    Optional,
    Sequence,
    TypedDict,
    cast,
)

from ansible.module_utils.basic import AnsibleModule
from ansible_collections.bodsch.scm.plugins.module_utils.forgejo.api import ForgejoApi
from ansible_collections.bodsch.scm.plugins.module_utils.forgejo.users import (
    ForgejoApiUsers,
)
from ansible_collections.bodsch.scm.plugins.module_utils.forgejo.utils import (
    check_existing_users,
    validate_users,
)

DOCUMENTATION = r"""
---
module: forgejo_user
author: Bodo 'bodsch' Schulz <bodo@boone-schulz.de>
version_added: 1.0.0

short_description: Manage Forgejo users.
description:
  - Manage users in a Forgejo instance via its REST API.
  - Can list existing users, create missing users, and delete existing users.

options:
  users:
    description:
      - List of users to manage.
      - Each entry should include C(username) and optionally C(state).
      - For C(state=present), C(password) and C(email) are required.
      - For C(state=absent), only C(username) is required.
      - If the list is empty, the module returns the current user list.
    required: false
    type: list
    elements: dict
    default: []

  server:
    description:
      - Base URL of the Forgejo instance.
    required: false
    default: http://localhost:3000
    type: str

  api_user:
    description:
      - Username for Forgejo API authentication.
    required: false
    type: str

  api_password:
    description:
      - Password for Forgejo API authentication.
    required: false
    type: str
    no_log: true
"""

EXAMPLES = r"""
- name: List all users in Forgejo
  bodsch.scm.forgejo_user:
    server: http://forgejo.local:3000
    api_user: admin
    api_password: secret
    users: []
  register: result

- name: Create a new user
  bodsch.scm.forgejo_user:
    server: http://forgejo.local:3000
    api_user: admin
    api_password: secret
    users:
      - username: "jdoe"
        password: "securePassw0rd!"
        email: "jdoe@example.com"
        state: present

- name: Delete a user
  bodsch.scm.forgejo_user:
    server: http://forgejo.local:3000
    api_user: admin
    api_password: secret
    users:
      - username: "olduser"
        state: absent
"""

RETURN = r"""
state:
  description: Detailed result entries.
  returned: always
  type: list
  elements: dict

changed:
  description: Indicates if any user was created or deleted (or would be in check mode).
  returned: always
  type: bool

failed:
  description: Indicates if any user action failed or invalid inputs were provided.
  returned: always
  type: bool

users:
  description: List of existing users (returned when `users` is empty).
  returned: when users is empty
  type: list
"""


UserState = Literal["present", "absent"]


class PerUserResult(TypedDict, total=False):
    """Result payload for a single user operation."""

    failed: bool
    changed: bool
    msg: str
    status_code: int


class ModuleResult(TypedDict, total=False):
    """Top-level module result structure."""

    changed: bool
    failed: bool
    msg: str
    state: List[Dict[str, PerUserResult]]
    users: List[Mapping[str, Any]]


class ForgejoUsers:
    """
    Manage Forgejo users via the REST API.

    The class performs:
    - Retrieval of existing users.
    - Validation of requested user definitions.
    - Create/delete operations depending on desired state.
    - Check mode support: only reports intended changes.
    """

    def __init__(self, module: AnsibleModule) -> None:
        """
        Initialize the user manager from Ansible parameters.

        Args:
            module: Active AnsibleModule instance.
        """
        self.module = module

        self.users: List[Dict[str, Any]] = cast(
            List[Dict[str, Any]], module.params.get("users", [])
        )
        self.server: str = cast(
            str, module.params.get("server", "http://localhost:3000")
        )
        self.api_user: Optional[str] = module.params.get("api_user")
        self.api_password: Optional[str] = module.params.get("api_password")

        base_url = f"{self.server.rstrip('/')}/api/v1"

        api = ForgejoApi(
            module=self.module,
            base_url=base_url,
            username=self.api_user,
            password=self.api_password,
            # token="..."  # not exposed by this module
        )
        self.users_api = ForgejoApiUsers(api)

    def run(self) -> ModuleResult:
        """
        Execute the module logic.

        Returns:
            A structured result dict for `module.exit_json()`.
        """
        state: List[Dict[str, PerUserResult]] = []

        status_code, existing_users = self.users_api.list_users()
        if status_code not in (200, 201):
            self.module.fail_json(
                msg=f"Failed to list users (status_code={status_code})."
            )

        # "List mode": when users is empty, return the fetched list.
        if not self.users:
            return {
                "changed": False,
                "failed": False,
                "msg": "Returned existing users.",
                "users": cast(List[Mapping[str, Any]], existing_users),
                "state": [],
            }

        valid_users, invalid_users = validate_users(users=self.users)

        if invalid_users:
            state.append(
                {
                    "invalid_users": {
                        "failed": True,
                        "changed": False,
                        "msg": "One or more user definitions are invalid.",
                    }
                }
            )

        existing_to_process, missing_to_process = check_existing_users(
            new_users=valid_users,
            existing=existing_users,
        )

        # Process existing users
        for user in existing_to_process:
            username = str(user.get("username") or "").strip()
            desired = cast(UserState, user.get("state", "present"))

            if not username:
                state.append(
                    {
                        "<missing-username>": {
                            "failed": True,
                            "changed": False,
                            "msg": "Missing username.",
                        }
                    }
                )
                continue

            if desired == "absent":
                # delete
                if self.module.check_mode:
                    state.append(
                        {
                            username: {
                                "failed": False,
                                "changed": True,
                                "msg": "User would be deleted (check mode).",
                            }
                        }
                    )
                    continue

                sc, _ = self.users_api.delete_user(username=username)
                if sc == 204:
                    state.append(
                        {
                            username: {
                                "failed": False,
                                "changed": True,
                                "msg": "The user has been successfully deleted.",
                                "status_code": sc,
                            }
                        }
                    )
                else:
                    state.append(
                        {
                            username: {
                                "failed": True,
                                "changed": False,
                                "msg": f"Failed to delete user (status_code={sc}).",
                                "status_code": sc,
                            }
                        }
                    )
            else:
                # present + already exists -> no-op
                state.append(
                    {
                        username: {
                            "failed": False,
                            "changed": False,
                            "msg": "User already exists.",
                        }
                    }
                )

        # Process missing users
        for user in missing_to_process:
            username = str(user.get("username") or "").strip()
            desired = cast(UserState, user.get("state", "present"))

            if not username:
                state.append(
                    {
                        "<missing-username>": {
                            "failed": True,
                            "changed": False,
                            "msg": "Missing username.",
                        }
                    }
                )
                continue

            if desired == "present":
                password = user.get("password")
                email = user.get("email")

                # Defensive validation: create requires password/email.
                if not password or not email:
                    state.append(
                        {
                            username: {
                                "failed": True,
                                "changed": False,
                                "msg": "Missing password/email for user creation.",
                            }
                        }
                    )
                    continue

                if self.module.check_mode:
                    state.append(
                        {
                            username: {
                                "failed": False,
                                "changed": True,
                                "msg": "User would be created (check mode).",
                            }
                        }
                    )
                    continue

                sc, _ = self.users_api.create_user(
                    username=username, password=password, email=email
                )
                if sc == 201:
                    state.append(
                        {
                            username: {
                                "failed": False,
                                "changed": True,
                                "msg": "The user has been successfully created.",
                                "status_code": sc,
                            }
                        }
                    )
                else:
                    state.append(
                        {
                            username: {
                                "failed": True,
                                "changed": False,
                                "msg": f"Failed to create user (status_code={sc}).",
                                "status_code": sc,
                            }
                        }
                    )
            else:
                # absent + missing -> no-op
                state.append(
                    {
                        username: {
                            "failed": False,
                            "changed": False,
                            "msg": "User does not exist (nothing to delete).",
                        }
                    }
                )

        changed = self._aggregate_changed(state)
        failed = self._aggregate_failed(state)

        return {"changed": changed, "failed": failed, "state": state}

    @staticmethod
    def _aggregate_changed(state: Sequence[Mapping[str, PerUserResult]]) -> bool:
        """
        Aggregate per-entry `changed` flags.

        Args:
            state: State entries as produced by this module.

        Returns:
            True if any entry indicates a change, otherwise False.
        """
        for entry in state:
            for _, payload in entry.items():
                if payload.get("changed"):
                    return True
        return False

    @staticmethod
    def _aggregate_failed(state: Sequence[Mapping[str, PerUserResult]]) -> bool:
        """
        Aggregate per-entry `failed` flags.

        Args:
            state: State entries as produced by this module.

        Returns:
            True if any entry indicates a failure, otherwise False.
        """
        for entry in state:
            for _, payload in entry.items():
                if payload.get("failed"):
                    return True
        return False


def main() -> None:
    """
    Ansible module entry point.

    Defines arguments and executes `ForgejoUsers`.
    """
    specs: Dict[str, Any] = dict(
        users=dict(required=False, type="list", elements="dict", default=[]),
        server=dict(required=False, default="http://localhost:3000", type="str"),
        api_user=dict(required=False, type="str"),
        api_password=dict(required=False, type="str", no_log=True),
    )

    module = AnsibleModule(
        argument_spec=specs,
        supports_check_mode=True,
    )

    manager = ForgejoUsers(module)
    result = manager.run()
    module.exit_json(**result)


if __name__ == "__main__":
    main()
