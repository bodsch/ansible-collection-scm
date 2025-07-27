#!/usr/bin/python
# -*- coding: utf-8 -*-

# (c) 2023, Bodo Schulz <bodo@boone-schulz.de>
# Apache (see LICENSE or https://opensource.org/licenses/Apache-2.0)

from __future__ import absolute_import, print_function
import os
from ansible.module_utils.basic import AnsibleModule
from ansible_collections.bodsch.scm.plugins.module_utils.forgejo_user import ForgejoUser
from ansible_collections.bodsch.core.plugins.module_utils.module_results import results

__metaclass__ = type

DOCUMENTATION = r"""
---
module: forgejo_user
author: Bodo 'bodsch' Schulz <bodo@boone-schulz.de>
version_added: 1.0.0

short_description: Forgejo User handling.
description:
    - Forgejo User handling.

options:
  state:
    description:
      - (C(present))
      - (C(absent))
      - (C(list))
      - (C(check))
    required: true
    default: present

  admin:
    description: TBD
    required: false
    type: bool
    default: false

  username:
    description: TBD
    required: false
    type: str

  password:
    description: TBD
    required: false
    type: str
    no_log: true

  email:
    description: TBD
    required: false
    type: str

  working_dir:
    description: TBD
    required: true
    type: str

  config:
    description: TBD
    required: false
    default: /etc/forgejo/forgejo.ini
    type: str
"""

EXAMPLES = r"""
- name: list forgejo users
  remote_user: "{{ forgejo_system_user }}"
  become_user: "{{ forgejo_system_user }}"
  become: true
  bodsch.scm.forgejo_user:
    state: list

- name: check forgejo admin user '{{ forgejo_admin_user.username }}'
  remote_user: "{{ forgejo_system_user }}"
  become_user: "{{ forgejo_system_user }}"
  become: true
  bodsch.scm.forgejo_user:
    state: check
    username: "{{ forgejo_admin_user.username }}"
  register: forgejo_admin_user_present

- name: create admin user
  remote_user: "{{ forgejo_system_user }}"
  become_user: "{{ forgejo_system_user }}"
  become: true
  bodsch.scm.forgejo_user:
    admin: true
    username: "{{ forgejo_admin_user.username }}"
    password: "{{ forgejo_admin_user.password }}"
    email: "{{ forgejo_admin_user.email }}"
"""

RETURN = r"""
"""

# ----------------------------------------------------------------------


class ForgejoUsers(ForgejoUser):
    """
    """
    module = None

    def __init__(self, module):
        """
        """
        self.module = module

        self.users = module.params.get("users")
        self.working_dir = module.params.get("working_dir")
        self.config = module.params.get("config")

        super().__init__(
            module,
            working_dir=self.working_dir,
            forgejo_config=self.config
        )

    def run(self):
        """
        """
        result = dict(
            changed=False,
            failed=True
        )

        result_state = []

        if os.path.isdir(self.working_dir):
            os.chdir(self.working_dir)

        existing_users = self.list_users()

        self.module.log(msg=f"  existing_users : '{existing_users}'")
        self.module.log(msg=f"  wanted users   : '{self.users}'")

        valid_users, invalid_users = self.validate_users()

        # self.module.log(msg=f"  valid_users    : '{valid_users}'")
        # self.module.log(msg=f"  invalid_users  : '{invalid_users}'")

        _, non_existing_users = self.check_existing_users(new_users=valid_users, existing=existing_users)

        # self.module.log(msg=f"  existing_users    : '{existing_users}'")
        # self.module.log(msg=f"  non_existing_users: '{non_existing_users}'")

        if len(invalid_users) > 0:
            result_state.append({
                "invalid users": {
                    "failed": True,
                    "changed": False,
                    "usernames": ", ".join([x.get("username") for x in invalid_users])
                }
            })

        if len(existing_users) > 0:
            result_state.append({
                "existing users": {
                    "failed": False,
                    "changed": False,
                    "usernames": ", ".join([x.get("username") for x in existing_users])
                }
            })

        for user in non_existing_users:
            """
            """
            user_state = user.get("state", "present")
            user_name = user.get("username")
            user_password = user.get("password")
            user_email = user.get("email")

            res = {}

            if user_state == "present":
                res[user_name] = self.add_user(
                    username=user_name,
                    password=user_password,
                    email=user_email
                )

                pass
            elif user_state == "absent":
                """
                    Deleting users is currently not supported.
                """
                res[user_name] = {
                    "failed": False,
                    "changed": False,
                    "msg": "Deleting users is currently not supported."
                }

            else:
                """
                    what!?
                """
                res[user_name] = {
                    "failed": True,
                    "changed": False,
                    "msg": f"The state “{user_state}” is not supported! Only 'present' or 'absent' are permitted."
                }
                pass

            result_state.append(res)

        _state, _changed, _failed, state, changed, failed = results(self.module, result_state)

        result = dict(
            changed=_changed,
            failed=_failed,
            state=result_state
        )

        return result


def main():
    """
    """
    specs = dict(
        users=dict(
            required=True,
            type=list
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

    kc = ForgejoUsers(module)
    result = kc.run()

    module.log(msg=f"= result : '{result}'")

    module.exit_json(**result)


# import module snippets
if __name__ == '__main__':
    main()

"""
root@instance:/# forgejo --help
NAME:
   Forgejo - A painless self-hosted Git service

USAGE:
   forgejo [global options] command [command options] [arguments...]

VERSION:
   1.19.0 built with GNU Make 4.1, go1.20.2 : bindata, sqlite, sqlite_unlock_notify

DESCRIPTION:
   By default, forgejo will start serving using the webserver with no
arguments - which can alternatively be run by running the subcommand web.

COMMANDS:
   web              Start Forgejo web server
   serv             This command should only be called by SSH shell
   hook             Delegate commands to corresponding Git hooks
   dump             Dump Forgejo files and database
   cert             Generate self-signed certificate
   admin            Command line interface to perform common administrative operations
   generate         Command line interface for running generators
   migrate          Migrate the database
   keys             This command queries the Forgejo database to get the authorized command for a given ssh key fingerprint
   convert          Convert the database
   doctor           Diagnose and optionally fix problems
   manager          Manage the running forgejo process
   embedded         Extract embedded resources
   migrate-storage  Migrate the storage
   docs             Output CLI documentation
   dump-repo        Dump the repository from git/github/forgejo/gitlab
   restore-repo     Restore the repository from disk
   help, h          Shows a list of commands or help for one command

GLOBAL OPTIONS:
   --port value, -p value         Temporary port number to prevent conflict (default: "3000")
   --install-port value           Temporary port number to run the install page on to prevent conflict (default: "3000")
   --pid value, -P value          Custom pid file path (default: "/run/forgejo.pid")
   --quiet, -q                    Only display Fatal logging errors until logging is set-up
   --verbose                      Set initial logging to TRACE level until logging is properly set-up
   --custom-path value, -C value  Custom path file path (default: "/usr/bin/custom")
   --config value, -c value       Custom configuration file path (default: "/usr/bin/custom/conf/app.ini")
   --version, -v                  print the version
   --work-path value, -w value    Set the forgejo working path (default: "/usr/bin")
   --help, -h                     show help

DEFAULT CONFIGURATION:
     CustomPath:  /usr/bin/custom
     CustomConf:  /usr/bin/custom/conf/app.ini
     AppPath:     /usr/bin/forgejo
     AppWorkPath: /usr/bin
"""
