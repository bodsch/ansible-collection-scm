#!/usr/bin/python
# -*- coding: utf-8 -*-

# (c) 2023-2025, Bodo Schulz <bodo@boone-schulz.de>
# Apache (see LICENSE or https://opensource.org/licenses/Apache-2.0)

from __future__ import absolute_import, print_function
import os

from ansible.module_utils.basic import AnsibleModule
from ansible_collections.bodsch.scm.plugins.module_utils.forgejo_user import ForgejoUser

__metaclass__ = type

DOCUMENTATION = r"""
---
module: forgejo_user
author: Bodo 'bodsch' Schulz (@bodsch)
version_added: "1.0.0"

short_description: Manage Forgejo admin users.
description:
  - This module allows to create an admin user in a Forgejo installation
    if it does not already exist.
  - Deletion of users is currently not supported.
  - The module must be executed as the Forgejo service user to access the database.

options:
  username:
    description:
      - The Forgejo username to create if it does not exist.
    required: false
    type: str

  password:
    description:
      - Password for the Forgejo user.
    required: false
    type: str
    no_log: true

  email:
    description:
      - Email address of the Forgejo user.
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
  remote_user: "{{ forgejo_system_user }}"
  become_user: "{{ forgejo_system_user }}"
  become: true
  bodsch.scm.forgejo_admin_user:
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

failed:
  description: Indicates if the module encountered a failure.
  returned: always
  type: bool
  sample: false

msg:
  description: Human-readable message with details about the operation.
  returned: always
  type: str
  sample: "user admin already created."
"""

# ----------------------------------------------------------------------


class ForgejoAdminUser(ForgejoUser):
    """
    """
    module = None

    def __init__(self, module):
        """
        """
        self.module = module

        self.state = module.params.get("state")
        self.admin = module.params.get("admin")
        self.username = module.params.get("username")
        self.password = module.params.get("password")
        self.email = module.params.get("email")

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

        if os.path.isdir(self.working_dir):
            os.chdir(self.working_dir)

        existing_users = self.list_users()

        # self.module.log(msg=f"  existing_users : '{existing_users}'")

        # if self.state == "present":
        if not existing_users.get(self.username):
            result = self.add_user(
                username=self.username,
                password=self.password,
                email=self.email,
                admin_user=True
            )
        else:
            result = dict(
                changed=False,
                msg=f"user {self.username} already created."
            )

        if self.state == "absent":
            result["msg"] = "This part is currently not supported."

        return result


def main():
    """
    """
    specs = dict(
        username=dict(
            required=False,
            type=str
        ),
        password=dict(
            required=False,
            type=str,
            no_log=True,
        ),
        email=dict(
            required=False,
            type=str
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

    kc = ForgejoAdminUser(module)
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
