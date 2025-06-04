#!/usr/bin/python3
# -*- coding: utf-8 -*-

# (c) 2020-2025, Bodo Schulz <bodo@boone-schulz.de>
# Apache (see LICENSE or https://opensource.org/licenses/Apache-2.0)

from __future__ import absolute_import, division, print_function
import os
import shutil
import grp
import pwd
import datetime

from ansible.module_utils.basic import AnsibleModule
from ansible_collections.bodsch.scm.plugins.module_utils.forgejo_ini import ForgejoIni
# from ansible_collections.bodsch.scm.plugins.module_utils.forgejo_config_parser import ForgejoConfigParser
from ansible_collections.bodsch.core.plugins.module_utils.diff import SideBySide

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
        """ """
        """
        Annahme: self.config ist Pfad zu forgejo.ini, self.new_config zu forgejo.new,
        self.ignore_map ist das Dict für ignore_keys, self.owner/group usw. existieren.
        """
        result = dict(
            failed=False,
            changed=False,
            msg="forgejo.ini is up-to-date."
        )

        # 1) Wenn config nicht existiert: neu kopieren
        if not os.path.exists(self.config):
            shutil.copyfile(self.new_config, self.config)
            shutil.chown(self.config, self.owner, self.group)
            return dict(
                failed=False,
                changed=True,
                msg="forgejo.ini was created successfully."
            )

        # 2) Sonst manuell beide Dateien einlesen, OHNE ConfigParser
        org = ForgejoIni(self.module, path=self.config, ignore_keys=self.ignore_map)
        new = ForgejoIni(self.module, path=self.new_config, ignore_keys=self.ignore_map)

        # 3) Alle möglichen Sektionen sammeln
        all_sections = set(org.data.keys()) | set(new.data.keys()) | set(self.ignore_map.keys())

        # 4) Struktur, um Unterschiede zu protokollieren
        #    Zum Beispiel: differences = { section: {"status": ..., "cs_base": ..., "cs_new": ...}, ... }
        differences = {}

        for section in sorted(all_sections):
            # self.module.log(f"  section: '{section}'")
            cs_base = ""
            cs_new = ""
            # a) Items (Key→Value) aus Base/ New holen, oder {} falls fehlt
            items_base = org.data.get(section, {})
            items_new = new.data.get(section, {})

            if len(items_base) > 0:
                cs_base = org.checksum_section(section)
            if len(items_new) > 0:
                cs_new = new.checksum_section(section)

            # self.module.log(f"    org data: '{items_base}' type: {type(items_base)} size: {len(items_base)}")
            # self.module.log(f"    new data: '{items_new}' type: {type(items_new)} size: {len(items_new)}")

            # c) Status bestimmen:
            #    - "org"      : Sektion nur in Base vorhanden
            #    - "new"      : Sektion nur in New vorhanden
            #    - "identical": in beiden vorhanden & gleiche Hashes
            #    - "modified" : in beiden vorhanden, aber unterschiedliche Hashes

            if cs_base == cs_new:
                status = "identical"
            else:
                if section in org.data and section not in new.data:
                    status = "org"
                    self.module.log("  only in org data")
                elif section not in org.data and section in new.data:
                    status = "new"
                    self.module.log("  only in new data")
                else:  # existiert in beiden
                    if cs_base == cs_new:
                        status = "identical"
                    else:
                        status = "modified"

            differences[section] = {
                "status": status,
                "cs_base": cs_base,
                "cs_new": cs_new,
                "items_base": items_base,
                "items_new": items_new,
            }

        # 5) Prüfen, ob irgendwo eine Sektion nicht "identical" ist
        sections_with_changes = [sec for sec, info in differences.items() if info["status"] != "identical"]
        if not sections_with_changes:
            # Alles identisch – kein Merge nötig
            return result

        # org_clean = org.get_cleaned_string()
        # new_clean = new.get_cleaned_string()

        # side_by_side = SideBySide(
        #     module=self.module,
        #     left=org.get_cleaned_string(),
        #     right=new.get_cleaned_string()
        # )
        # self.module.log(f"{side_by_side.diff(width=140)}")

        # 6) Wenn hier, dann mindestens eine Sektion tatsächlich geändert/neu/gelöscht
        #    Wir können jetzt sections_with_changes ausgeben oder im Log schreiben, z.B.:
        # self.module.log("Die folgenden Sektionen haben Unterschiede:")
        # for sec in sections_with_changes:
        #     info = differences[sec]
        #     self.module.log(f"  section '{sec}'")
        #     self.module.log(f"  {info}")

        merged_path = os.path.join(os.path.dirname(self.config), "forgejo.merged")

        # # 7) Backup-Logik wie gehabt
        # self.create_backup()

        ForgejoIni.merge(
            module=self.module,
            base_path=self.config,
            new_path=self.new_config,
            output_path=merged_path,
            ignore_keys=self.ignore_map
        )

        shutil.copyfile(merged_path, self.config)
        shutil.chown(self.config, self.owner, self.group)

        return dict(
            failed=False,
            changed=True,
            msg="forgejo.ini was changed."
        )

    def run_o(self):
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

        org = ForgejoConfigParser(self.module, path=self.config, ignore_keys=self.ignore_map)
        new = ForgejoConfigParser(self.module, path=self.new_config, ignore_keys=self.ignore_map)

        # org_clean = org.get_cleaned_string()
        # new_clean = new.get_cleaned_string()

        # side_by_side = SideBySide(module=self.module, left=org_clean, right=new_clean)
        # self.module.log(f"{side_by_side.diff(width=140)}")

        if not org.is_equal_to(new):
            self.module.log("Konfiguration hat sich geändert.")
            self.module.log(f"Original SHA256 : {org.checksum()}")
            self.module.log(f"Neu SHA256      : {new.checksum()}")

            side_by_side = SideBySide(module=self.module, left=self.config, right=self.new_config)
            self.module.log(f"{side_by_side.diff()}")

            merged_config = os.path.join(os.path.dirname(self.config), "forgejo.merged")

            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M")
            basename, ext = os.path.splitext(self.config)

            backup_config = f"{basename}_{timestamp}{ext}"

            self.module.log(f"merged_config : {merged_config}")
            self.module.log(f"backup_config : {backup_config}")

            new.merge_into(base_path=self.config, output_path=merged_config)

            # shutil.move(merged_config, self.config)
            os.rename(self.config, backup_config)
            shutil.copyfile(merged_config, self.config)
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
