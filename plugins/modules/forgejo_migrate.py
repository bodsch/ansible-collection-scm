#!/usr/bin/python
# -*- coding: utf-8 -*-

# (c) 2023, Bodo Schulz <bodo@boone-schulz.de>
# Apache (see LICENSE or https://opensource.org/licenses/Apache-2.0)

from __future__ import absolute_import, print_function

from ansible.module_utils.basic import AnsibleModule


__metaclass__ = type

DOCUMENTATION = r"""
---
module: forgejo_migrate
author: Bodo 'bodsch' Schulz (@bodsch)
version_added: "1.0.0"

short_description: Migrate a Forgejo database.
description:
  - This module runs the C(forgejo migrate) command to perform a database migration.
  - It must be executed as the Forgejo service user to have access to the working directory and configuration.
  - A successful run will indicate a changed state, as the migration modifies the database schema.

options:
  command:
    description:
      - The command to execute. Currently only C(migrate) is supported.
    required: false
    type: str
    choices: [ migrate ]
    default: migrate

  parameters:
    description:
      - Additional command-line parameters for the migrate command.
      - Currently unused.
    required: false
    type: list
    elements: str
    default: []

  working_dir:
    description:
      - Path to the Forgejo working directory (C(--work-path) argument).
      - Typically the home directory of the Forgejo service user.
    required: false
    type: str
    default: "/var/lib/forgejo"

  environment:
    description:
      - Runtime environment for the migration (currently informational only).
    required: false
    type: str
    default: "prod"

  config:
    description:
      - Path to the Forgejo configuration file (C(--config) argument).
    required: false
    type: str
    default: "/etc/forgejo/forgejo.ini"

notes:
  - This module always reports C(changed=true) when the migration runs successfully.
  - On error, the module returns C(failed=true) with the Forgejo CLI error message.
"""

EXAMPLES = r"""
- name: migrate forgejo database
  remote_user: "{{ forgejo_remote_user }}"
  become_user: "{{ forgejo_system_user }}"
  become: true
  bodsch.scm.forgejo_migrate:
    config: "{{ forgejo_config_dir }}/forgejo.ini"
    working_dir: "{{ forgejo_working_dir }}"
"""

RETURN = r"""
changed:
  description: Indicates whether the database migration was performed.
  returned: always
  type: bool
  sample: true

failed:
  description: Indicates if the module encountered an error.
  returned: always
  type: bool
  sample: false

msg:
  description: Human-readable message about the migration result.
  returned: always
  type: str
  sample: "Database successful migrated."
"""

# ----------------------------------------------------------------------


class ForgejoMigrate(object):
    """
    """
    module = None

    def __init__(self, module):
        """
        """
        self.module = module

        # self._console = module.get_bin_path('console', False)

        self.command = module.params.get("command")
        self.parameters = module.params.get("parameters")
        self.working_dir = module.params.get("working_dir")
        self.environment = module.params.get("environment")
        self.config = module.params.get("config")

        self.forgejo_bin = module.get_bin_path('forgejo', True)

    def run(self):
        """
        """

        result = self.migrate()

        return result

    def migrate(self):
        """
            forgejo migrate --help --config /etc/forgejo/forgejo.ini
        """

        args_list = [
            self.forgejo_bin,
            "--work-path", self.working_dir,
            "--config", self.config,
            "migrate"
        ]

        # self.module.log(msg=f"  args_list : '{args_list}'")

        rc, out, err = self._exec(args_list)

        if rc == 0:
            return dict(
                failed=False,
                changed=True,
                msg="Database successful migrated."
            )
        else:
            return dict(
                failed=True,
                msg=err
            )

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
        command=dict(
            default="migrate",
            choices=[
                "migrate",
            ]
        ),
        parameters=dict(
            required=False,
            type=list,
            default=[]
        ),
        working_dir=dict(
            required=False,
            default="/var/lib/forgejo",
            type=str
        ),
        environment=dict(
            required=False,
            default="prod"
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

    kc = ForgejoMigrate(module)
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

"""
  upgrade forgejo:

  see: https://github.com/go-forgejo/forgejo/blob/main/contrib/upgrade.sh

# stop forgejo, create backup, replace binary, restart forgejo
echo "Flushing forgejo queues at $(date)"
forgejocmd manager flush-queues
echo "Stopping forgejo at $(date)"
$service_stop
echo "Creating backup in $forgejohome"
forgejocmd dump $backupopts
echo "Updating binary at $forgejobin"
cp -f "$forgejobin" "$forgejobin.bak" && mv -f "$binname" "$forgejobin"
$service_start
$service_status
"""

""" https://docs.forgejo.com/administration/command-line """
