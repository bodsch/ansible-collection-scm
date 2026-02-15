#!/usr/bin/python
# -*- coding: utf-8 -*-

"""
Ansible module for managing Forgejo LDAP authentication sources via the Forgejo CLI.

This module ensures an LDAP (Bind DN) authentication source exists in a Forgejo
installation. It is designed to be idempotent by storing a checksum of the desired
configuration and only applying changes when the configuration differs.

Security note:
- The bind password is treated as a secret and is NOT written to disk in cleartext.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Literal, Mapping, Optional, Tuple, TypedDict, cast

from ansible.module_utils.basic import AnsibleModule
from ansible_collections.bodsch.core.plugins.module_utils.checksum import Checksum
from ansible_collections.bodsch.core.plugins.module_utils.directory import (
    create_directory,
)

DOCUMENTATION = r"""
---
module: forgejo_auth
author: Bodo 'bodsch' Schulz <bodo@boone-schulz.de>
version_added: "1.0.0"

short_description: Manage Forgejo LDAP authentication entries.
description:
  - Manage LDAP (Bind DN) authentication sources in Forgejo via the Forgejo CLI.
  - Adds or updates an LDAP authentication configuration.
  - Tracks configuration changes using a checksum to determine whether updates are required.
  - Deletion (state=absent) is currently not implemented.

options:
  state:
    description:
      - Desired state of the LDAP authentication source.
      - C(present) ensures the authentication source is configured.
      - C(absent) is currently not implemented and results in no change.
    required: false
    type: str
    choices: [present, absent]
    default: present

  name:
    description:
      - Unique name of the LDAP authentication source in Forgejo.
    required: true
    type: str

  active:
    description:
      - Whether the authentication source is active in Forgejo.
    required: false
    default: true
    type: bool

  security_protocol:
    description:
      - Security protocol used to connect to the LDAP server.
    required: false
    default: Unencrypted
    type: str
    choices: [Unencrypted, LDAPS, StartTLS]

  skip_tls_verify:
    description:
      - Skip TLS certificate verification when connecting via LDAPS or StartTLS.
    required: false
    default: true
    type: bool

  hostname:
    description:
      - Hostname or IP address of the LDAP server.
    required: true
    type: str

  port:
    description:
      - Port of the LDAP server (e.g. 389 for LDAP or 636 for LDAPS).
      - If omitted, the Forgejo CLI default is used.
    required: false
    type: int

  user_search_base:
    description:
      - LDAP search base used to look up users.
    required: true
    type: str

  filters:
    description:
      - Optional LDAP filters for users, admins, or restricted accounts.
    required: false
    type: dict

  allow_deactivate_all:
    description:
      - Allow empty search results to deactivate all users.
    required: false
    default: false
    type: bool

  attributes:
    description:
      - Mapping of LDAP attributes to Forgejo fields.
    required: true
    type: dict

  skip_local_2fa:
    description:
      - Skip local 2FA for LDAP users.
    required: false
    default: false
    type: bool

  bind_dn:
    description:
      - DN of the LDAP user used to bind and search the directory.
    required: true
    type: str

  bind_password:
    description:
      - Password for the bind DN.
    required: true
    type: str
    no_log: true

  attributes_in_bind:
    description:
      - Fetch attributes in bind DN context.
    required: false
    default: false
    type: bool

  synchronize_users:
    description:
      - Enable user synchronization.
    required: false
    default: false
    type: bool

  working_dir:
    description:
      - Forgejo working directory.
    required: false
    default: /var/lib/forgejo
    type: str

  config:
    description:
      - Path to the Forgejo configuration file.
    required: false
    default: /etc/forgejo/forgejo.ini
    type: str

  cache_dir:
    description:
      - Directory used to store checksum/state for idempotency.
      - If omitted, defaults to C(<working_dir>/.ansible/forgejo).
    required: false
    type: str
"""

EXAMPLES = r"""
- name: enable ldap authentication
  remote_user: "{{ forgejo_remote_user }}"
  become_user: "{{ forgejo_system_user }}"
  become: true
  bodsch.scm.forgejo_auth:
    working_dir: /var/lib/forgejo
    config: /etc/forgejo/forgejo.ini
    name: "{{ forgejo_auths.ldap.name | default(omit) }}"
    state: "{{ forgejo_auths.ldap.state | default(omit) }}"
    active: "{{ forgejo_auths.ldap.active | default(omit) }}"
    security_protocol: "{{ forgejo_auths.ldap.security_protocol | default(omit) }}"
    skip_tls_verify: "{{ forgejo_auths.ldap.skip_tls_verify | default(omit) }}"
    hostname: "{{ forgejo_auths.ldap.hostname | default(omit) }}"
    port: "{{ forgejo_auths.ldap.port | default(omit) }}"
    user_search_base: "{{ forgejo_auths.ldap.user_search_base | default(omit) }}"
    filters:
      user: "{{ forgejo_auths.ldap.filters.user | default(omit) }}"
      admin: "{{ forgejo_auths.ldap.filters.admin | default(omit) }}"
      restricted: "{{ forgejo_auths.ldap.filters.restricted | default(omit) }}"
    allow_deactivate_all: "{{ forgejo_auths.ldap.allow_deactivate_all | default(omit) }}"
    attributes:
      username: "{{ forgejo_auths.ldap.attributes.username | default(omit) }}"
      firstname: "{{ forgejo_auths.ldap.attributes.firstname | default(omit) }}"
      surname: "{{ forgejo_auths.ldap.attributes.surname | default(omit) }}"
      email: "{{ forgejo_auths.ldap.attributes.email | default(omit) }}"
      public_ssh_key: "{{ forgejo_auths.ldap.attributes.public_ssh_key | default(omit) }}"
      avatar: "{{ forgejo_auths.ldap.attributes.avatar | default(omit) }}"
    skip_local_2fa: "{{ forgejo_auths.ldap.skip_local_2fa | default(omit) }}"
    bind_dn: "{{ forgejo_auths.ldap.bind_dn | default(omit) }}"
    bind_password: "{{ forgejo_auths.ldap.bind_password | default(omit) }}"
    attributes_in_bind: "{{ forgejo_auths.ldap.attributes_in_bind | default(omit) }}"
    synchronize_users: "{{ forgejo_auths.ldap.synchronize_users | default(omit) }}"
"""

RETURN = r"""
changed:
  description: Whether the LDAP authentication configuration was changed.
  returned: always
  type: bool

failed:
  description: Whether the module failed (only returned on non-fatal paths; fatal errors use fail_json()).
  returned: always
  type: bool

msg:
  description: Human-readable message about the action taken.
  returned: always
  type: str
"""


State = Literal["present", "absent"]
SecurityProtocol = Literal["Unencrypted", "LDAPS", "StartTLS"]


class ModuleResult(TypedDict):
    """Typed return structure for this Ansible module."""

    changed: bool
    failed: bool
    msg: str


@dataclass(frozen=True)
class LdapConfig:
    """
    Typed representation of the LDAP auth configuration.

    This is used to:
    - Build the Forgejo CLI argument list in a deterministic way.
    - Compute a stable checksum for idempotency.
    """

    name: str
    active: bool
    security_protocol: SecurityProtocol
    skip_tls_verify: bool
    hostname: str
    port: Optional[int]
    user_search_base: str
    filter_user: Optional[str]
    filter_admin: Optional[str]
    filter_restricted: Optional[str]
    allow_deactivate_all: bool
    attribute_username: Optional[str]
    attribute_firstname: Optional[str]
    attribute_surname: Optional[str]
    attribute_email: Optional[str]
    attribute_public_ssh_key: Optional[str]
    attribute_avatar: Optional[str]
    skip_local_2fa: bool
    bind_dn: str
    bind_password: str
    attributes_in_bind: bool
    synchronize_users: bool
    working_dir: str
    config: str

    def to_cli_args(self) -> List[str]:
        """
        Convert this configuration into Forgejo CLI arguments.

        Returns:
            List of CLI arguments (excluding the initial `forgejo admin auth ...` tokens).
        """
        args: List[str] = [
            "--config",
            self.config,
            "--work-path",
            self.working_dir,
            "--name",
            self.name,
            "--host",
            self.hostname,
            "--bind-dn",
            self.bind_dn,
            "--bind-password",
            self.bind_password,
            "--user-search-base",
            self.user_search_base,
            "--security-protocol",
            self.security_protocol,
        ]

        if self.port is not None:
            args += ["--port", str(self.port)]

        if self.filter_user:
            args += ["--user-filter", self.filter_user]
        if self.filter_admin:
            args += ["--admin-filter", self.filter_admin]
        if self.filter_restricted:
            args += ["--restricted-filter", self.filter_restricted]

        if self.allow_deactivate_all:
            args += ["--allow-deactivate-all"]

        if self.attribute_username:
            args += ["--username-attribute", self.attribute_username]
        if self.attribute_firstname:
            args += ["--firstname-attribute", self.attribute_firstname]
        if self.attribute_surname:
            args += ["--surname-attribute", self.attribute_surname]
        if self.attribute_email:
            args += ["--email-attribute", self.attribute_email]
        if self.attribute_public_ssh_key:
            args += ["--public-ssh-key-attribute", self.attribute_public_ssh_key]
        if self.attribute_avatar:
            args += ["--avatar-attribute", self.attribute_avatar]

        if self.skip_local_2fa:
            args += ["--skip-local-2fa"]

        if self.attributes_in_bind:
            args += ["--attributes-in-bind"]

        if self.synchronize_users:
            args += ["--synchronize-users"]
        else:
            args += ["--disable-synchronize-users"]

        if not self.active:
            args += ["--not-active"]

        if self.skip_tls_verify:
            args += ["--skip-tls-verify"]

        return args

    def checksum_payload(self) -> Dict[str, Any]:
        """
        Create a JSON-serializable payload for checksum computation.

        The bind password is included only as a hash to avoid persisting secrets.

        Returns:
            Dictionary used as input for checksum computation.
        """
        pwd_hash = hashlib.sha256(self.bind_password.encode("utf-8")).hexdigest()
        payload = {
            "name": self.name,
            "active": self.active,
            "security_protocol": self.security_protocol,
            "skip_tls_verify": self.skip_tls_verify,
            "hostname": self.hostname,
            "port": self.port,
            "user_search_base": self.user_search_base,
            "filters": {
                "user": self.filter_user,
                "admin": self.filter_admin,
                "restricted": self.filter_restricted,
            },
            "allow_deactivate_all": self.allow_deactivate_all,
            "attributes": {
                "username": self.attribute_username,
                "firstname": self.attribute_firstname,
                "surname": self.attribute_surname,
                "email": self.attribute_email,
                "public_ssh_key": self.attribute_public_ssh_key,
                "avatar": self.attribute_avatar,
            },
            "skip_local_2fa": self.skip_local_2fa,
            "bind_dn": self.bind_dn,
            "bind_password_sha256": pwd_hash,
            "attributes_in_bind": self.attributes_in_bind,
            "synchronize_users": self.synchronize_users,
            "working_dir": self.working_dir,
            "config": self.config,
        }
        return payload


class ForgejoAuth:
    """
    Manager for Forgejo LDAP authentication sources.

    Responsibilities:
    - Determine whether an auth source exists by name.
    - Add or update the auth source using the Forgejo CLI.
    - Track configuration changes via checksum files for idempotency.
    """

    def __init__(self, module: AnsibleModule) -> None:
        """
        Initialize the manager from module parameters.

        Args:
            module: Active AnsibleModule instance.
        """
        self.module = module

        self.state: State = cast(State, module.params.get("state", "present"))

        self.working_dir: str = module.params.get("working_dir", "/var/lib/forgejo")
        self.config: str = module.params.get("config", "/etc/forgejo/forgejo.ini")

        cache_dir_param: Optional[str] = module.params.get("cache_dir")
        self.cache_directory: str = cache_dir_param or os.path.join(
            self.working_dir, ".ansible", "forgejo"
        )

        self.forgejo_bin: str = module.get_bin_path("forgejo", required=True)

        # Files used for idempotency (checksum) and debugging (sanitized config).
        self.checksum_file: str = os.path.join(
            self.cache_directory, "forgejo_auth.sha256"
        )
        self.config_snapshot_file: str = os.path.join(
            self.cache_directory, "forgejo_auth.json"
        )

        self.cfg: LdapConfig = self._load_config()

    def _load_config(self) -> LdapConfig:
        """
        Load and validate module parameters into a typed LdapConfig.

        Returns:
            LdapConfig instance built from module parameters.
        """
        filters: Mapping[str, Any] = cast(
            Mapping[str, Any], self.module.params.get("filters") or {}
        )
        attributes: Mapping[str, Any] = cast(
            Mapping[str, Any], self.module.params.get("attributes") or {}
        )

        return LdapConfig(
            name=cast(str, self.module.params.get("name")),
            active=bool(self.module.params.get("active", True)),
            security_protocol=cast(
                SecurityProtocol,
                self.module.params.get("security_protocol", "Unencrypted"),
            ),
            skip_tls_verify=bool(self.module.params.get("skip_tls_verify", True)),
            hostname=cast(str, self.module.params.get("hostname")),
            port=self.module.params.get("port"),
            user_search_base=cast(str, self.module.params.get("user_search_base")),
            filter_user=cast(Optional[str], filters.get("user")),
            filter_admin=cast(Optional[str], filters.get("admin")),
            filter_restricted=cast(Optional[str], filters.get("restricted")),
            allow_deactivate_all=bool(
                self.module.params.get("allow_deactivate_all", False)
            ),
            attribute_username=cast(Optional[str], attributes.get("username")),
            attribute_firstname=cast(Optional[str], attributes.get("firstname")),
            attribute_surname=cast(Optional[str], attributes.get("surname")),
            attribute_email=cast(Optional[str], attributes.get("email")),
            attribute_public_ssh_key=cast(
                Optional[str], attributes.get("public_ssh_key")
            ),
            attribute_avatar=cast(Optional[str], attributes.get("avatar")),
            skip_local_2fa=bool(self.module.params.get("skip_local_2fa", False)),
            bind_dn=cast(str, self.module.params.get("bind_dn")),
            bind_password=cast(str, self.module.params.get("bind_password")),
            attributes_in_bind=bool(
                self.module.params.get("attributes_in_bind", False)
            ),
            synchronize_users=bool(self.module.params.get("synchronize_users", False)),
            working_dir=self.working_dir,
            config=self.config,
        )

    def _validate_paths(self) -> None:
        """
        Validate working directory and configuration file paths.

        Raises:
            module.fail_json on validation errors.
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

    def run(self) -> ModuleResult:
        """
        Execute the desired state operation.

        Returns:
            ModuleResult for exit_json().
        """
        self._validate_paths()

        os.chdir(self.working_dir)

        create_directory(directory=self.cache_directory, mode="0750")

        if self.state == "absent":
            return {
                "changed": False,
                "failed": False,
                "msg": "state=absent is not implemented for forgejo_auth.",
            }

        # present
        desired_checksum = self._compute_desired_checksum()
        current_checksum = self._read_checksum_file()

        if current_checksum == desired_checksum:
            return {
                "changed": False,
                "failed": False,
                "msg": "The authentication has not been changed.",
            }

        auth_exists, auth_id = self.auth_exists(self.cfg.name)

        if self.module.check_mode:
            action = "update" if auth_exists else "create"
            return {
                "changed": True,
                "failed": False,
                "msg": f"LDAP Auth {self.cfg.name} would be {action}d (check mode).",
            }

        if not auth_exists:
            result = self.add_auth()
        else:
            result = self.update_auth(auth_id=auth_id)

        # Persist idempotency data only on successful change.
        if not result["failed"] and result["changed"]:
            self._write_checksum_file(desired_checksum)
            self._write_sanitized_snapshot()

        return result

    def auth_exists(self, name: str) -> Tuple[bool, str]:
        """
        Check whether an authentication source exists and return its ID.

        This method uses:
        `forgejo admin auth list --vertical-bars`

        Args:
            name: Authentication name to look up.

        Returns:
            Tuple of (exists, auth_id). auth_id is an empty string if not found.
        """
        args_list = [
            self.forgejo_bin,
            "admin",
            "auth",
            "list",
            "--vertical-bars",
            "--work-path",
            self.cfg.working_dir,
            "--config",
            self.cfg.config,
        ]

        rc, out, err = self._exec(args_list)
        if rc != 0:
            self.module.fail_json(
                msg=f"Failed to list authentication sources: {err or out}"
            )

        # Expected format: "ID | Name | Type | Enabled"
        pattern = re.compile(
            r"^\s*(?P<id>\d+)\s*\|\s*"
            r"(?P<name>[^\|]+?)\s*\|\s*"
            r"(?P<type>[^\|]+?)\s*\|\s*"
            r"(?P<enabled>[^\|]+?)\s*$"
        )

        for line in out.splitlines()[1:]:
            m = pattern.search(line)
            if not m:
                continue
            gd = m.groupdict()
            found_name = (gd.get("name") or "").strip()
            if found_name == name:
                auth_id = (gd.get("id") or "").strip()
                auth_type = (gd.get("type") or "").strip()
                self.module.log(
                    msg=f"found authentication: {found_name} with type {auth_type}"
                )
                return True, auth_id

        return False, ""

    def add_auth(self) -> ModuleResult:
        """
        Create a new LDAP authentication source via the Forgejo CLI.

        Returns:
            ModuleResult indicating success/failure and change status.
        """
        args_list = [self.forgejo_bin, "admin", "auth", "add-ldap"]
        args_list += self.cfg.to_cli_args()

        rc, out, err = self._exec(args_list)
        if rc == 0:
            return {
                "failed": False,
                "changed": True,
                "msg": f"LDAP Auth {self.cfg.name} successfully created.",
            }
        return {"failed": True, "changed": False, "msg": err or out}

    def update_auth(self, auth_id: str) -> ModuleResult:
        """
        Update an existing LDAP authentication source via the Forgejo CLI.

        Args:
            auth_id: The numeric auth source ID as returned by `forgejo admin auth list`.

        Returns:
            ModuleResult indicating success/failure and change status.
        """
        if not auth_id:
            return {
                "failed": True,
                "changed": False,
                "msg": "Cannot update auth source: missing auth_id.",
            }

        args_list = [self.forgejo_bin, "admin", "auth", "update-ldap", "--id", auth_id]
        args_list += self.cfg.to_cli_args()

        rc, out, err = self._exec(args_list)
        if rc == 0:
            return {
                "failed": False,
                "changed": True,
                "msg": f"LDAP Auth {self.cfg.name} successfully updated.",
            }
        return {"failed": True, "changed": False, "msg": err or out}

    def _compute_desired_checksum(self) -> str:
        """
        Compute a stable checksum for the desired configuration.

        Uses a payload that excludes secrets (bind password is included as a hash).

        Returns:
            Hex-encoded checksum string.
        """
        checksum = Checksum(self.module)
        payload = self.cfg.checksum_payload()
        serialized = json.dumps(payload, indent=2, sort_keys=True) + "\n"
        return cast(str, checksum.checksum(serialized))

    def _read_checksum_file(self) -> Optional[str]:
        """
        Read the previously stored checksum, if available.

        Backward-compatibility:
        - If the new checksum file does not exist, this method tries to derive the
          checksum from the old JSON snapshot file (legacy behavior).

        Returns:
            The stored checksum or None if not available.
        """
        p = Path(self.checksum_file)
        if p.exists() and p.is_file():
            try:
                return p.read_text(encoding="utf-8").strip() or None
            except OSError:
                return None

        # Legacy fallback: derive from snapshot file if it exists.
        legacy = Path(self.config_snapshot_file)
        if legacy.exists() and legacy.is_file():
            try:
                checksum = Checksum(self.module)
                return cast(str, checksum.checksum_from_file(str(legacy)))
            except Exception:
                return None

        return None

    def _write_checksum_file(self, checksum_value: str) -> None:
        """
        Persist the current checksum.

        Args:
            checksum_value: The checksum string to store.
        """
        Path(self.checksum_file).write_text(
            checksum_value.strip() + "\n", encoding="utf-8"
        )

    def _write_sanitized_snapshot(self) -> None:
        """
        Write a sanitized JSON snapshot of module parameters for debugging.

        The bind password is not stored; only a placeholder is written.
        """
        data: Dict[str, Any] = dict(self.module.params)
        if "bind_password" in data:
            data["bind_password"] = "***"
        Path(self.config_snapshot_file).write_text(
            json.dumps(data, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

    def _exec(self, commands: List[str]) -> Tuple[int, str, str]:
        """
        Execute a command using Ansible's run_command.

        Args:
            commands: Command token list.

        Returns:
            Tuple (rc, stdout, stderr). Does not raise on non-zero rc.
        """
        rc, out, err = self.module.run_command(commands, check_rc=False)
        if rc != 0:
            self.module.log(msg=f"rc={rc}")
            if out:
                self.module.log(msg=f"out: {out}")
            if err:
                self.module.log(msg=f"err: {err}")
        return int(rc), cast(str, out), cast(str, err)


def main() -> None:
    """
    Ansible module entry point.

    Defines argument specification and executes the ForgejoAuth manager.
    """
    specs: Dict[str, Any] = dict(
        state=dict(
            type="str", required=False, default="present", choices=["present", "absent"]
        ),
        name=dict(type="str", required=True),
        active=dict(type="bool", required=False, default=True),
        security_protocol=dict(
            type="str",
            required=False,
            choices=["Unencrypted", "LDAPS", "StartTLS"],
            default="Unencrypted",
        ),
        skip_tls_verify=dict(type="bool", required=False, default=True),
        hostname=dict(type="str", required=True),
        port=dict(type="int", required=False),
        user_search_base=dict(type="str", required=True),
        filters=dict(type="dict", required=False, default={}),
        allow_deactivate_all=dict(type="bool", required=False, default=False),
        attributes=dict(type="dict", required=True),
        skip_local_2fa=dict(type="bool", required=False, default=False),
        bind_dn=dict(type="str", required=True),
        bind_password=dict(type="str", required=True, no_log=True),
        attributes_in_bind=dict(type="bool", required=False, default=False),
        synchronize_users=dict(type="bool", required=False, default=False),
        working_dir=dict(type="str", required=False, default="/var/lib/forgejo"),
        config=dict(type="str", required=False, default="/etc/forgejo/forgejo.ini"),
        cache_dir=dict(type="str", required=False),
    )

    module = AnsibleModule(
        argument_spec=specs,
        supports_check_mode=True,
    )

    manager = ForgejoAuth(module)
    result = manager.run()
    module.exit_json(**result)


if __name__ == "__main__":
    main()
