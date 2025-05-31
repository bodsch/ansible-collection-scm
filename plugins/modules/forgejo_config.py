#!/usr/bin/python3
# -*- coding: utf-8 -*-

# (c) 2020-2025, Bodo Schulz <bodo@boone-schulz.de>
# Apache (see LICENSE or https://opensource.org/licenses/Apache-2.0)

from __future__ import absolute_import, division, print_function
import hashlib
import os
import shutil
import grp
import pwd

from ansible.module_utils.basic import AnsibleModule

from io import StringIO
try:
    from configparser import ConfigParser
except ImportError:
    # ver. < 3.0
    from ConfigParser import ConfigParser


DOCUMENTATION = """
---
module: forgejo_config
author: Bodo 'bodsch' Schulz <bodo@boone-schulz.de>
version_added: 1.4.0

short_description: extended handling of config updates to avoid restarts.
description:
  - Avoids restarts if a forgejo.ini has been written.
  - After the first start of a forgojo instance, a new variable INTERNAL_TOKEN is inserted in the `security` section.
  - The same happens under oauth2 with JWT_SECRET.
  - These variables are overwritten when the file is created with `ansible.builtin.template`.
  - As a result, the Forgejo was restarted with every run, which is not necessary.

"""

EXAMPLES = """
- name: update forgejo config
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
"""

# ---------------------------------------------------------------------------------------


class ForgejoConfig(object):
    """
    """
    module = None

    def __init__(self, module):
        """
        """
        self.module = module

        self.config = module.params.get("config")
        self.new_config = module.params.get("new_config")
        self.owner = module.params.get("owner")
        self.group = module.params.get("group")

    def run(self):
        """
        """
        result = dict(
            failed=False,
            changed=False,
            msg="forgejo.ini is up-to-date."
        )

        ignore_map = {
            'oauth2': ['JWT_SECRET'],
            'security': ['INTERNAL_TOKEN']
        }

        if not os.path.exists(self.config):

            # uid, gid = self.get_file_ownership(self.new_config)
            # self.module.log(msg=f"  {uid} :: {gid}")

            shutil.copyfile(self.new_config, self.config)
            shutil.chown(self.config, self.owner, self.group)

            return dict(
                failed=False,
                changed=True,
                msg="forgejo.ini was created successfully."
            )

        changed = self.compare_configs(self.config, self.new_config, ignore_map=ignore_map)

        if changed:
            self.transfer_keys(
                file1=self.config,
                file2=self.new_config,
                section_keys_to_transfer={
                    'security': ['INTERNAL_TOKEN'],
                    'oauth2': ['JWT_SECRET']
                },
                output_file='/etc/forgejo/forgejo.ini'
            )

            return dict(
                failed=False,
                changed=True,
                msg="forgejo.ini was changed."
            )

        return result

    def read_ini_with_global_section(self, path, global_section="__global__"):
        """
        """
        with open(path, 'r', encoding='utf-8') as f:
            lines = f.readlines()

        self.module.log(f"{lines}")

        modified_lines = []
        section_started = False

        for i, line in enumerate(lines):
            stripped = line.strip()
            if not stripped or stripped.startswith(';'):
                modified_lines.append(line)
                continue
            if stripped.startswith('['):
                section_started = True
                break
            else:
                break

        # Nur wenn keine Section direkt am Anfang kommt
        if not section_started:
            modified_lines = [f'[{global_section}]\n'] + lines
        else:
            modified_lines = lines

        self.module.log(f"{modified_lines}")

        config = ConfigParser()
        config.optionxform = str

        try:
            config.read_file(StringIO(''.join(modified_lines)))
        except Exception as e:
            self.module.log(f"ERROR {e}")

        return config

    def compare_configs(self, file1, file2, ignore_map=None):

        changed = False
        config1 = self.read_ini_with_global_section(file1)
        config2 = self.read_ini_with_global_section(file2)

        ignore_map = {k.lower(): [key.lower() for key in v] for k, v in (ignore_map or {}).items()}

        all_sections = set(config1.sections()) | set(config2.sections())

        for section in all_sections:
            if section not in config1 or section not in config2:
                continue

            ignore_keys = set(ignore_map.get(section, []))

            checksum1 = self.section_checksum(config1, section, ignore_keys)
            checksum2 = self.section_checksum(config2, section, ignore_keys)

            if checksum1 != checksum2:
                changed = True
                self.module.log(f"Difference in section [{section}]")
                _added, _removed, _changed = self.diff_section(config1, config2, section)

                if _added or _removed or _changed:
                    for k, v in _added:
                        self.module.log(f"  + added  : {k} = {v}")
                    for k, v in _removed:
                        self.module.log(f"  - removed: {k} = {v}")
                    for k, v1, v2 in _changed:
                        self.module.log(f"  ~ changed: {k} = {v1} → {v2}")

        self.module.log(f"= changed: {changed}")

        return changed

    def section_checksum(self, config, section, ignore_keys=None):
        """
        """
        ignore_keys = ignore_keys or set()
        items = [(k, v) for k, v in config[section].items() if k.lower() not in ignore_keys]
        items.sort()
        concat = ''.join(f'{k}={v}' for k, v in items)

        return hashlib.md5(concat.encode('utf-8')).hexdigest()

    def transfer_keys(self, file1, file2, section_keys_to_transfer, output_file):
        """
        """
        config1 = self.read_ini_with_global_section(file1)
        config2 = self.read_ini_with_global_section(file2)

        for section, keys in section_keys_to_transfer.items():
            if not config1.has_section(section):
                continue

            if not config2.has_section(section):
                config2.add_section(section)

            for key in keys:
                if config1.has_option(section, key):
                    value = config1.get(section, key)
                    config2.set(section, key, value)

        # Datei schreiben
        with open(output_file, 'w', encoding='utf-8') as f:
            config2.write(f)

    def diff_section(self, config1, config2, section, ignore_keys=None):
        ignore_keys = set(ignore_keys or [])
        keys1 = {k: v for k, v in config1.items(section)} if config1.has_section(section) else {}
        keys2 = {k: v for k, v in config2.items(section)} if config2.has_section(section) else {}

        added = []
        removed = []
        changed = []

        for k in keys1:
            if k in ignore_keys:
                continue
            if k not in keys2:
                removed.append((k, keys1[k]))
            elif keys1[k] != keys2[k]:
                changed.append((k, keys1[k], keys2[k]))
        for k in keys2:
            if k in ignore_keys or k in keys1:
                continue
            added.append((k, keys2[k]))

        return added, removed, changed

    def get_file_ownership(self, filename):
        return (
            pwd.getpwuid(os.stat(filename).st_uid).pw_name,
            grp.getgrgid(os.stat(filename).st_gid).gr_name
        )

def main():
    """
    """
    specs = dict(
        config=dict(
            required=False,
            default="/etc/forgejo/forgejo.ini",
            type=str
        ),
        new_config=dict(
            required=False,
            default="/etc/forgejo/forgejo.new",
            type=str
        ),
        owner=dict(
            required=False,
            type='str',
            default="forgejo"
        ),
        group=dict(
            required=False,
            type='str',
            default="forgejo"
        ),
    )

    module = AnsibleModule(
        argument_spec=specs,
        supports_check_mode=False,
    )

    config = ForgejoConfig(module)
    result = config.run()

    module.log(msg=f"= result : '{result}'")

    module.exit_json(**result)


# import module snippets
if __name__ == '__main__':
    main()
