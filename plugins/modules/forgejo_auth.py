#!/usr/bin/python
# -*- coding: utf-8 -*-

# (c) 2023, Bodo Schulz <bodo@boone-schulz.de>
# Apache (see LICENSE or https://opensource.org/licenses/Apache-2.0)

from __future__ import absolute_import, print_function
import os
import json
import re

from ansible.module_utils.basic import AnsibleModule
from ansible_collections.bodsch.core.plugins.module_utils.directory import create_directory
from ansible_collections.bodsch.core.plugins.module_utils.checksum import Checksum


__metaclass__ = type

DOCUMENTATION = r"""
---
module: forgejo_auth
author: Bodo 'bodsch' Schulz <bodo@boone-schulz.de>
version_added: 1.0.0

short_description: Forgejo Authentication.
description:
    - Forgejo Authentication.

options:
  state:
    description:
      - (C(present))
      - (C(absent))
    required: true
    default: present

  name:
    description: TBD
    required: true
    type: str

  active:
    description: TBD
    required: false
    default: true
    type: bool

  security_protocol:
    description:
      - (C(Unencrypted))
      - (C(LDAPS))
      - (C(StartTLS))
    required: false
    default: Unencrypted
    type: str

  skip_tls_verify:
    description: TBD
    required: false
    default: true
    type: bool

  hostname:
    description: TBD
    required: true
    type: str

  port:
    description: TBD
    required: false
    type: str

  user_search_base:
    description: TBD
    required: true
    type: str

  filters:
    description: TBD
    required: false
    type: dict

  allow_deactivate_all:
    description: TBD
    required: false
    default: false
    type: bool

  attributes:
    description: TBD
    required: true
    type: dict

  skip_local_2fa:
    description: TBD
    required: false
    default: false
    type: bool

  bind_dn:
    description: TBD
    required: true
    type: str

  bind_password:
    description: TBD
    required: true
    type: str
    no_log: true

  attributes_in_bind:
    description: TBD
    required: false
    default: false
    type: str

  synchronize_users:
    description: TBD
    required: false
    default: false
    type: bool

  working_dir:
    description: TBD
    required: true
    default: /var/lib/forgejo
    type: str

  config:
    description: TBD
    required: false
    default: /etc/forgejo/forgejo.ini
    type: str
"""

EXAMPLES = r"""
- name: enable ldap authentication
  remote_user: "{{ forgejo_system_user }}"
  become_user: "{{ forgejo_system_user }}"
  become: true
  bodsch.scm.forgejo_auth:
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
"""

# ----------------------------------------------------------------------


class ForgejoAuth(object):
    """
    """
    module = None

    def __init__(self, module):
        """
        """
        self.module = module

        self.state = module.params.get("state")
        self.name = module.params.get("name")
        self.active = module.params.get("active")
        self.security_protocol = module.params.get("security_protocol")
        self.skip_tls_verify = module.params.get("skip_tls_verify")
        self.hostname = module.params.get("hostname")
        self.port = module.params.get("port")
        self.user_search_base = module.params.get("user_search_base")
        self.filters = module.params.get("filters")  # { user, admin, restricted }
        self.filter_user = self.filters.get("user", None)
        self.filter_admin = self.filters.get("admin", None)
        self.filter_restricted = self.filters.get("restricted", None)
        self.allow_deactivate_all = module.params.get("allow_deactivate_all")
        self.attributes = module.params.get("attributes")  # { username, firstname, surename, email, public_ssh_key, avatar }
        self.attribute_username = self.attributes.get("username", None)
        self.attribute_firstname = self.attributes.get("firstname", None)
        self.attribute_surname = self.attributes.get("surname", None)
        self.attribute_email = self.attributes.get("email", None)
        self.attribute_public_ssh_key = self.attributes.get("public_ssh_key", None)
        self.attribute_avatar = self.attributes.get("avatar", None)
        self.skip_local_2fa = module.params.get("skip_local_2fa")
        self.bind_dn = module.params.get("bind_dn")
        self.bind_password = module.params.get("bind_password")
        self.attributes_in_bind = module.params.get("attributes_in_bind")
        self.synchronize_users = module.params.get("synchronize_users")
        self.working_dir = module.params.get("working_dir")
        self.config = module.params.get("config")

        self.forgejo_bin = module.get_bin_path('forgejo', True)
        self.cache_directory = os.path.dirname(self.config)
        self.checksum_file_name = os.path.join(self.cache_directory, "forgejo_auth.checksum")
        self.auth_config_json_file = os.path.join(self.cache_directory, "forgejo_auth.json")

    def run(self):
        """
        """
        create_directory(directory=self.cache_directory, mode="0750")

        checksum = Checksum(self.module)

        failed = False

        if self.state == "present":
            new_checksum = checksum.checksum(json.dumps(self.module.params, indent=2, sort_keys=False) + "\n")
            old_checksum = checksum.checksum_from_file(self.auth_config_json_file)

            changed = not (new_checksum == old_checksum)
            new_file = False
            msg = "The authentication has not been changed."

            # self.module.log(f'{json.dumps(self.module.params, indent=2, sort_keys=False)}' + "\n")
            #
            # self.module.log(f" changed       : {changed}")
            # self.module.log(f" new_checksum  : {new_checksum}")
            # self.module.log(f" old_checksum  : {old_checksum}")

            # auth_exists, auth_id = self.auth_exists(self.name)
            #
            # self.module.log(f" auth_exists   : {auth_exists}")
            # self.module.log(f" auth_id       : {auth_id}")

            if changed:
                auth_exists, auth_id = self.auth_exists(self.name)

                if not auth_exists:
                    _result = self.add_auth()
                    failed = _result.get("failed")
                    changed = _result.get("changed")
                    msg = _result.get("msg")
                else:
                    _result = self.update_auth(auth_id)
                    failed = _result.get("failed")
                    changed = _result.get("changed")
                    msg = _result.get("msg")

                self.__write_config(self.auth_config_json_file, self.module.params)

            if new_file:
                msg = "The authentication was successfully created."
                # result = dict(
                #     changed=False,
                #     msg=f"authentication {self.name} already created."
                # )

        else:
            pass

        return dict(
            changed=changed,
            failed=failed,
            msg=msg,
        )

    def auth_exists(self, name):
        """
            su forgejo -c "/usr/bin/forgejo --config /etc/forgejo/forgejo.ini --work-path /var/lib/forgejo admin auth list"
        """
        args_list = [
            self.forgejo_bin,
            "admin",
            "auth",
            "list",
            "--vertical-bars",
            "--work-path", self.working_dir,
            "--config", self.config,
        ]

        result = (False, 0)
        rc, out, err = self._exec(args_list)

        pattern = re.compile(
            r'^\s*(?P<id>\d+)\s*\|\s*'
            r'(?P<name>[^\|]+?)\s*\|\s*'
            r'(?P<type>[^\|]+?)\s*\|\s*'
            r'(?P<enabled>\w+)\s*$'
        )
        match = next((m.groupdict() for s in out.splitlines()[1:] if (m := pattern.search(s))), None)

        if match and isinstance(match, dict):
            auth_id = match.get('id')
            auth_name = match.get('name')
            auth_type = match.get('type')
            # auth_enabled = match.get('enabled')

            self.module.log(msg=f"  found authentication : {auth_name} with type {auth_type.strip()}")

            result = (True, auth_id)

        return result

    def add_auth(self):
        """
            su forgejo -c "forgejo admin auth add-ldap
               --name
               --security-protocol LDAPS
               --host
               --port
               --bind-dn
               --bind-password
               --user-search-base <ie: “DC=company,DC=int”
               --user-filter
               --admin-filter
               --username-attribute
        """
        args_list = [
            self.forgejo_bin,
            "admin",
            "auth",
            "add-ldap"
        ]

        args_list += self.__auth_params()

        rc, out, err = self._exec(args_list)

        if rc == 0:
            return dict(
                failed=False,
                changed=True,
                msg=f"LDAP Auth {self.name} successful created."
            )
        else:
            return dict(
                failed=True,
                msg=err
            )

    # TODO
    def update_auth(self, auth_id):
        """
        """
        args_list = [
            self.forgejo_bin,
            "admin",
            "auth",
            "update-ldap",
            "--id",
            auth_id
        ]

        args_list += self.__auth_params()

        rc, out, err = self._exec(args_list)

        if rc == 0:
            return dict(
                failed=False,
                changed=True,
                msg=f"LDAP Auth {self.name} successful updated."
            )
        else:
            return dict(
                failed=True,
                msg=err
            )

    def __auth_params(self):

        args_list = [
            "--config", self.config,
            "--work-path", self.working_dir,
            "--name", self.name,
            "--host", self.hostname,
            "--port", self.port,
            "--bind-dn", self.bind_dn,
            "--bind-password", self.bind_password,
            "--user-search-base", self.user_search_base,
            "--security-protocol", self.security_protocol
        ]

        if self.filter_user:
            args_list += [
                "--user-filter", self.filter_user
            ]

        if self.filter_admin:
            args_list += [
                "--admin-filter", self.filter_admin
            ]

        if self.filter_restricted:
            args_list += [
                "--restricted-filter", self.filter_restricted
            ]

        if self.attribute_username:
            args_list += [
                "--username-attribute", self.attribute_username
            ]

        if self.attribute_firstname:
            args_list += [
                "--firstname-attribute", self.attribute_firstname
            ]

        if self.attribute_surname:
            args_list += [
                "--surname-attribute", self.attribute_surname
            ]

        if self.attribute_email:
            args_list += [
                "--email-attribute", self.attribute_email
            ]

        if self.attribute_public_ssh_key:
            args_list += [
                "--public-ssh-key-attribute", self.attribute_public_ssh_key
            ]

        if self.attribute_avatar:
            args_list += [
                "--avatar-attribute", self.attribute_avatar
            ]

        if not self.synchronize_users:
            args_list += [
                "--disable-synchronize-users"
            ]

        if not self.active:
            args_list += [
                "--not-active"
            ]

        if self.skip_tls_verify:
            args_list += [
                "--skip-tls-verify"
            ]

        return args_list

    def __write_config(self, file_name, data):
        """
        """
        with open(file_name, 'w') as fp:
            json_data = json.dumps(data, indent=2, sort_keys=False)
            fp.write(f'{json_data}\n')

    def _exec(self, commands, check_rc=True):
        """
        """
        rc, out, err = self.module.run_command(commands, check_rc=check_rc)
        # self.module.log(msg=f"  rc : '{rc}'")

        if rc != 0:
            self.module.log(msg=f"  out: '{out}'")
            self.module.log(msg=f"  err: '{err}'")

        return rc, out, err


def main():
    """
    """
    specs = dict(
        state=dict(
            default="present",
            choices=[
                "present",
                "absent"
            ]
        ),
        name=dict(
            required=True,
            type=str
        ),
        active=dict(
            required=False,
            type=bool,
            default=True
        ),
        security_protocol=dict(
            required=False,
            type=str,
            choices=[
                "Unencrypted",
                "LDAPS",
                "StartTLS"
            ],
            default="Unencrypted"
        ),
        skip_tls_verify=dict(
            required=False,
            type=bool,
            default=True
        ),
        hostname=dict(
            required=True,
            type=str,
        ),
        port=dict(
            required=False,
            type=str,
        ),
        user_search_base=dict(
            required=True,
            type=str
        ),
        filters=dict(
            required=False,
            type=dict
            # { user, admin, restricted }
        ),
        allow_deactivate_all=dict(
            required=False,
            type=bool,
            default=False
        ),
        attributes=dict(
            required=True,
            type=dict
            # { username, firstname, surename, email,public_ssh_key, avatar }
        ),
        skip_local_2fa=dict(
            required=False,
            type=bool,
            default=False
        ),
        bind_dn=dict(
            required=True,
            type=str
        ),
        bind_password=dict(
            required=True,
            type=str,
            no_log=True
        ),
        attributes_in_bind=dict(
            required=False,
            type=bool,
            default=False
        ),
        synchronize_users=dict(
            required=False,
            type=bool,
            default=False
        ),
        working_dir=dict(
            required=False,
            default="/var/lib/forgejo",
            type=str
        ),
        config=dict(
            required=False,
            default="/etc/forgejo/forgejo.ini",
            type=str
        )
    )

    module = AnsibleModule(
        argument_spec=specs,
        supports_check_mode=False,
    )

    kc = ForgejoAuth(module)
    result = kc.run()

    module.log(msg=f"= result : '{result}'")

    module.exit_json(**result)


# import module snippets
if __name__ == '__main__':
    main()

"""

## LDAP
```bash
forgejo admin auth add-ldap
    --name
    --security-protocol LDAPS
    --host
    --port
    --bind-dn
    --bind-password
    --user-search-base <ie: “DC=company,DC=int”
    --user-filter
    --admin-filter
    --username-attribute
```
root@instance:/# su forgejo -c "/usr/bin/forgejo --config /etc/forgejo/forgejo.ini --work-path /var/lib/forgejo admin auth add-ldap --help"
NAME:
   Forgejo admin auth add-ldap - Add new LDAP (via Bind DN) authentication source

USAGE:
   Forgejo admin auth add-ldap [command options] [arguments...]

OPTIONS:
   --name value                      Authentication name.
   --not-active                      Deactivate the authentication source.
   --active                          Activate the authentication source.
   --security-protocol value         Security protocol name.
   --skip-tls-verify                 Disable TLS verification.
   --host value                      The address where the LDAP server can be reached.
   --port value                      The port to use when connecting to the LDAP server. (default: 0)
   --user-search-base value          The LDAP base at which user accounts will be searched for.
   --user-filter value               An LDAP filter declaring how to find the user record that is attempting to authenticate.
   --admin-filter value              An LDAP filter specifying if a user should be given administrator privileges.
   --restricted-filter value         An LDAP filter specifying if a user should be given restricted status.
   --allow-deactivate-all            Allow empty search results to deactivate all users.
   --username-attribute value        The attribute of the user’s LDAP record containing the user name.
   --firstname-attribute value       The attribute of the user’s LDAP record containing the user’s first name.
   --surname-attribute value         The attribute of the user’s LDAP record containing the user’s surname.
   --email-attribute value           The attribute of the user’s LDAP record containing the user’s email address.
   --public-ssh-key-attribute value  The attribute of the user’s LDAP record containing the user’s public ssh key.
   --skip-local-2fa                  Set to true to skip local 2fa for users authenticated by this source
   --avatar-attribute value          The attribute of the user’s LDAP record containing the user’s avatar.
   --bind-dn value                   The DN to bind to the LDAP server with when searching for the user.
   --bind-password value             The password for the Bind DN, if any.
   --attributes-in-bind              Fetch attributes in bind DN context.
   --synchronize-users               Enable user synchronization.
   --disable-synchronize-users       Disable user synchronization.
   --page-size value                 Search page size. (default: 0)
   --custom-path value, -C value     Custom path file path (default: "/usr/bin/custom")
   --config value, -c value          Custom configuration file path (default: "/usr/bin/custom/conf/app.ini")
   --version, -v                     print the version
   --work-path value, -w value       Set the forgejo working path (default: "/usr/bin")


DEFAULT CONFIGURATION:
     CustomPath:  /usr/bin/custom
     CustomConf:  /etc/forgejo/forgejo.ini
     AppPath:     /usr/bin/forgejo
     AppWorkPath: /var/lib/forgejo


"""
