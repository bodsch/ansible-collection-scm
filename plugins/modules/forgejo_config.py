#!/usr/bin/python3
# -*- coding: utf-8 -*-

# (c) 2020-2025, Bodo Schulz <bodo@boone-schulz.de>
# Apache (see LICENSE or https://opensource.org/licenses/Apache-2.0)

from __future__ import absolute_import, division, print_function
import os
import shutil
import grp
import pwd

from ansible.module_utils.basic import AnsibleModule
from ansible_collections.bodsch.scm.plugins.module_utils.forgejo_config_parser import ForgejoConfigParser


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


class ForgejoConfigCompare(object):
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

        self.ignore_map = {
            'oauth2': ['JWT_SECRET'],
            'security': ['INTERNAL_TOKEN']
        }

    def run(self):
        """
        """
        result = dict(
            failed=False,
            changed=False,
            msg="forgejo.ini is up-to-date."
        )

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

        orig = ForgejoConfigParser(path=self.config, ignore_keys=self.ignore_map)
        new = ForgejoConfigParser(path=self.new_config, ignore_keys=self.ignore_map)

        if not orig.is_equal_to(new):
            # self.module.log("Konfiguration hat sich geändert.")
            # self.module.log(f"Original SHA256 : {orig.checksum()}")
            # self.module.log(f"Neu SHA256      : {new.checksum()}")

            new.merge_into(base_path=self.config, output_path="/run/forgejo.merged")

            shutil.move("/run/forgejo.merged", self.config)
            shutil.chown(self.config, self.owner, self.group)

            return dict(
                failed=False,
                changed=True,
                msg="forgejo.ini was changed."
            )

        return result

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

    config = ForgejoConfigCompare(module)
    result = config.run()

    module.log(msg=f"= result : '{result}'")

    module.exit_json(**result)


# import module snippets
if __name__ == '__main__':
    main()
