#!/usr/bin/python3
# -*- coding: utf-8 -*-

"""
Ansible module to compare and update Forgejo configuration files efficiently.

This module compares an existing Forgejo configuration file (typically `forgejo.ini`)
with a newly generated configuration file and applies changes only when relevant.

To avoid unnecessary service restarts, it can ignore specific auto-generated keys
that Forgejo may update at runtime (e.g., INTERNAL_TOKEN, JWT_SECRET).

Key features:
- Section-based comparison (via ForgejoIni checksums) with an ignore-map.
- Atomic replacement of the configuration file when changes are required.
- Ownership enforcement after updates/creation.
- Check mode support (reports changes without writing files).
"""

from __future__ import annotations

import grp
import os
import pwd
import shutil
import tempfile
from pathlib import Path
from typing import Any, Dict, Mapping, Optional, Sequence, TypedDict

from ansible.module_utils.basic import AnsibleModule
from ansible_collections.bodsch.scm.plugins.module_utils.forgejo.ini import ForgejoIni

DOCUMENTATION = r"""
---
module: forgejo_config
author: Bodo 'bodsch' Schulz (@bodsch)
version_added: "1.4.0"

short_description: Extended handling of Forgejo configuration updates to avoid unnecessary restarts.
description:
  - This module compares the existing Forgejo configuration file (forgejo.ini)
    with a new configuration file and applies only necessary changes.
  - It avoids restarting the Forgejo service when only internal tokens
    (like INTERNAL_TOKEN or JWT_SECRET) are changed by Forgejo itself.
  - If differences are detected in relevant configuration sections,
    the configuration file is updated and ownership is ensured.

options:
  config:
    description:
      - Path to the current Forgejo configuration file (forgejo.ini).
    required: false
    type: str
    default: "/etc/forgejo/forgejo.ini"

  new_config:
    description:
      - Path to the new configuration file to compare against the current one.
    required: false
    type: str
    default: "/etc/forgejo/forgejo.new"

  owner:
    description:
      - File owner of the Forgejo configuration file.
    required: false
    type: str
    default: "forgejo"

  group:
    description:
      - File group of the Forgejo configuration file.
    required: false
    type: str
    default: "forgejo"

notes:
  - Only updates the configuration file if relevant changes are detected.
  - Ignores automatic Forgejo-generated values such as INTERNAL_TOKEN
    in C(security) and JWT_SECRET in C(oauth2).
  - Supports check mode: changes are reported, no files are written.
"""

EXAMPLES = r"""
- name: Update Forgejo configuration without unnecessary restarts
  bodsch.scm.forgejo_config:
    config: "{{ forgejo_config_dir }}/forgejo.ini"
    new_config: "{{ forgejo_config_dir }}/forgejo.new"
    owner: forgejo
    group: forgejo
  register: forgejo_config
  notify:
    - restart forgejo
    - check if forgejo are available
"""

RETURN = r"""
changed:
  description: Indicates if the configuration file was modified.
  returned: always
  type: bool

failed:
  description: Indicates if the module encountered a failure.
  returned: always
  type: bool

msg:
  description: Short message describing the result.
  returned: always
  type: str
  sample: "forgejo.ini was changed."
"""


class ModuleResult(TypedDict):
    """Typed result structure returned by this module."""

    failed: bool
    changed: bool
    msg: str


IgnoreMap = Mapping[str, Sequence[str]]


class ForgejoConfigCompare:
    """
    Compare and update Forgejo configuration files.

    The comparison is performed section-by-section using `ForgejoIni` checksums.
    Sections and keys configured in `ignore_map` are excluded from checksum and merge
    operations to prevent changes caused by Forgejo runtime-generated secrets from
    triggering updates and restarts.

    This class performs:
    - Validation of input paths and owner/group values.
    - Config creation if missing.
    - Merge+replace when relevant changes exist.
    - Ownership enforcement on the resulting config file.
    """

    def __init__(self, module: AnsibleModule) -> None:
        """
        Initialize the comparer from Ansible module parameters.

        Args:
            module: The active AnsibleModule instance.
        """
        self.module = module

        self.config: str = str(module.params.get("config"))
        self.new_config: str = str(module.params.get("new_config"))
        self.owner: str = str(module.params.get("owner"))
        self.group: str = str(module.params.get("group"))

        # Keys that Forgejo may rewrite at runtime and should not trigger a config update.
        self.ignore_map: IgnoreMap = {
            "oauth2": ["JWT_SECRET"],
            "security": ["INTERNAL_TOKEN"],
        }

    def run(self) -> ModuleResult:
        """
        Execute the comparison and update flow.

        Returns:
            ModuleResult with keys: failed, changed, msg.
        """
        self._validate_inputs()

        os.chdir(self.working_dir)

        result: ModuleResult = {
            "failed": False,
            "changed": False,
            "msg": "forgejo.ini is up-to-date.",
        }

        config_path = Path(self.config)
        new_path = Path(self.new_config)

        # 1) Config does not exist -> create from new_config.
        if not config_path.exists():
            if self.module.check_mode:
                return {
                    "failed": False,
                    "changed": True,
                    "msg": "forgejo.ini would be created (check mode).",
                }

            self._atomic_copy(src=new_path, dst=config_path)
            self._ensure_ownership(config_path)
            return {
                "failed": False,
                "changed": True,
                "msg": "forgejo.ini was created successfully.",
            }

        # 2) Compare (section checksums) while ignoring volatile keys.
        org_ini = ForgejoIni(
            self.module, path=str(config_path), ignore_keys=dict(self.ignore_map)
        )
        new_ini = ForgejoIni(
            self.module, path=str(new_path), ignore_keys=dict(self.ignore_map)
        )

        if not self._relevant_changes_exist(org_ini, new_ini):
            return result

        # 3) Merge and replace.
        if self.module.check_mode:
            return {
                "failed": False,
                "changed": True,
                "msg": "forgejo.ini would be updated (check mode).",
            }

        merged_path = self._merge_to_tempfile(base_path=config_path, new_path=new_path)
        try:
            self._atomic_copy(src=merged_path, dst=config_path)
            self._ensure_ownership(config_path)
        finally:
            try:
                merged_path.unlink(missing_ok=True)  # py3.8+: missing_ok supported
            except TypeError:
                if merged_path.exists():
                    merged_path.unlink()

        return {"failed": False, "changed": True, "msg": "forgejo.ini was changed."}

    def _validate_inputs(self) -> None:
        """
        Validate module inputs (paths and owner/group).

        Raises:
            Calls module.fail_json() on validation errors.
        """
        config_path = Path(self.config)
        new_path = Path(self.new_config)

        # new_config must exist because it is the comparison source and creation source.
        if not new_path.exists() or not new_path.is_file():
            self.module.fail_json(
                msg=f"new_config '{self.new_config}' does not exist or is not a file."
            )

        # If config exists, it must be a file. If it doesn't exist, creation path is used.
        if config_path.exists() and not config_path.is_file():
            self.module.fail_json(
                msg=f"config '{self.config}' exists but is not a file."
            )

        # Validate owner/group early to get deterministic failures.
        try:
            pwd.getpwnam(self.owner)
        except KeyError:
            self.module.fail_json(
                msg=f"owner '{self.owner}' does not exist on the target system."
            )
        try:
            grp.getgrnam(self.group)
        except KeyError:
            self.module.fail_json(
                msg=f"group '{self.group}' does not exist on the target system."
            )

    def _relevant_changes_exist(self, org_ini: ForgejoIni, new_ini: ForgejoIni) -> bool:
        """
        Determine whether there are relevant config changes.

        The comparison is based on per-section checksums as computed by ForgejoIni.
        Sections that only differ in ignored keys will be treated as identical.

        Args:
            org_ini: Parsed original config.
            new_ini: Parsed new config.

        Returns:
            True if any relevant change is detected, otherwise False.
        """
        all_sections = self._collect_sections(org_ini, new_ini, self.ignore_map)

        for section in all_sections:
            items_org = org_ini.data.get(section, {})
            items_new = new_ini.data.get(section, {})

            cs_org = org_ini.checksum_section(section) if items_org else ""
            cs_new = new_ini.checksum_section(section) if items_new else ""

            if cs_org != cs_new:
                return True

        return False

    @staticmethod
    def _collect_sections(
        org_ini: ForgejoIni, new_ini: ForgejoIni, ignore_map: IgnoreMap
    ) -> Sequence[str]:
        """
        Collect a stable list of sections to compare.

        Args:
            org_ini: Parsed original config.
            new_ini: Parsed new config.
            ignore_map: Ignore map containing sections that should always be considered.

        Returns:
            Sorted list of section names.
        """
        sections = (
            set(org_ini.data.keys()) | set(new_ini.data.keys()) | set(ignore_map.keys())
        )
        return sorted(sections)

    def _merge_to_tempfile(self, base_path: Path, new_path: Path) -> Path:
        """
        Merge base and new config into a temporary file in the target directory.

        The temp file is created next to the destination to support atomic replacement.

        Args:
            base_path: Existing config file path.
            new_path: New config file path.

        Returns:
            Path to the merged temporary file.
        """
        target_dir = str(base_path.parent)

        fd, tmp_name = tempfile.mkstemp(
            prefix="forgejo.", suffix=".merged", dir=target_dir
        )
        os.close(fd)
        tmp_path = Path(tmp_name)

        ForgejoIni.merge(
            module=self.module,
            base_path=str(base_path),
            new_path=str(new_path),
            output_path=str(tmp_path),
            ignore_keys=dict(self.ignore_map),
        )

        return tmp_path

    def _atomic_copy(self, src: Path, dst: Path) -> None:
        """
        Copy `src` to `dst` via a temporary file and then atomically replace.

        This prevents partially written configuration files on failure.

        Args:
            src: Source file path.
            dst: Destination file path.

        Raises:
            Calls module.fail_json() if file operations fail.
        """
        try:
            dst_parent = dst.parent
            dst_parent.mkdir(parents=True, exist_ok=True)

            # Preserve mode from existing destination if present; otherwise take source mode.
            dst_mode: Optional[int] = None
            if dst.exists():
                dst_mode = dst.stat().st_mode & 0o7777

            fd, tmp_name = tempfile.mkstemp(
                prefix=dst.name + ".", suffix=".tmp", dir=str(dst_parent)
            )
            os.close(fd)
            tmp_path = Path(tmp_name)

            shutil.copyfile(str(src), str(tmp_path))

            if dst_mode is not None:
                os.chmod(str(tmp_path), dst_mode)

            os.replace(str(tmp_path), str(dst))
        except OSError as exc:
            self.module.fail_json(msg=f"Failed to write '{dst}': {exc}")

    def _ensure_ownership(self, path: Path) -> None:
        """
        Ensure file ownership matches the requested owner/group.

        Args:
            path: Path to apply ownership on.

        Raises:
            Calls module.fail_json() if chown fails.
        """
        try:
            shutil.chown(str(path), self.owner, self.group)
        except OSError as exc:
            self.module.fail_json(msg=f"Failed to set ownership on '{path}': {exc}")


def main() -> None:
    """
    Ansible module entry point.

    Defines argument specification and executes ForgejoConfigCompare.
    """
    specs: Dict[str, Any] = dict(
        config=dict(required=False, default="/etc/forgejo/forgejo.ini", type="str"),
        new_config=dict(required=False, default="/etc/forgejo/forgejo.new", type="str"),
        owner=dict(required=False, type="str", default="forgejo"),
        group=dict(required=False, type="str", default="forgejo"),
    )

    module = AnsibleModule(
        argument_spec=specs,
        supports_check_mode=True,
    )

    comparer = ForgejoConfigCompare(module)
    result = comparer.run()
    module.exit_json(**result)


if __name__ == "__main__":
    main()
