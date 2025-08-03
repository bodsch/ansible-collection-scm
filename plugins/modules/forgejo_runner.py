#!/usr/bin/python3
# -*- coding: utf-8 -*-

# (c) 2023, Bodo Schulz <bodo@boone-schulz.de>
# Apache (see LICENSE or https://opensource.org/licenses/Apache-2.0)

from __future__ import absolute_import, print_function
import os
import socket

from ansible.module_utils.basic import AnsibleModule


__metaclass__ = type

DOCUMENTATION = r"""
---
module: forgejo_runner
author: Bodo 'bodsch' Schulz (@bodsch)
version_added: "1.0.0"

short_description: Register a Forgejo Runner on a Forgejo Server.
description:
  - This module registers a Forgejo runner by creating a runner file using the C(forgejo-runner create-runner-file) command.
  - It identifies the runner by the current hostname and checks the provided runner list to find the matching entry.
  - If the runner is unknown, the module fails with a descriptive error.

options:
  command:
    description:
      - The command to execute. Currently only C(create_runner) is supported.
    required: false
    type: str
    choices: [ create_runner ]
    default: create_runner

  working_dir:
    description:
      - Directory where the runner registration will be performed.
      - Must exist on the remote host.
    required: true
    type: str

  runners:
    description:
      - List of known Forgejo runners including their C(name), C(secret), and C(instance).
      - The runner name must match the hostname of the target machine to register successfully.
    required: true
    type: list
    elements: dict

notes:
  - The module checks if the host's runner is in the runners list.
  - On success, it creates a runner file in the specified working directory.
"""


EXAMPLES = r"""
- name: append runner to {{ forgejo_runner_controller.hostname }}
  become_user: "{{ forgejo_runner_system_user }}"
  become: true
  bodsch.scm.forgejo_runner:
    command: create_runner
    working_dir: "{{ forgejo_runner_working_dir }}"
    runners: "{{ forgejo_runner_register | default([]) }}"

- name: Register this host as a Forgejo runner
  become_user: forgejo-runner
  become: true
  bodsch.scm.forgejo_runner:
    command: create_runner
    working_dir: "/var/lib/forgejo-runner"
    runners:
      - name: "runner01"
        secret: "abcdef123456"
        instance: "https://forgejo.example.com"

- name: Use dynamic runners list from inventory
  become_user: "{{ forgejo_runner_system_user }}"
  become: true
  bodsch.scm.forgejo_runner:
    working_dir: "{{ forgejo_runner_working_dir }}"
    runners: "{{ forgejo_runner_register | default([]) }}"
"""

RETURN = r"""
changed:
  description: Indicates if the runner registration caused changes.
  returned: always
  type: bool
  sample: true

failed:
  description: Indicates if the module failed to register the runner.
  returned: always
  type: bool
  sample: false

msg:
  description: Human-readable message about the result.
  returned: always
  type: str
  sample: "Runner runner01 succesfully registerd."
"""


# ----------------------------------------------------------------------


class ForgejoRunner(object):
    """
    """
    module = None

    def __init__(self, module):
        """
        """
        self.module = module

        # self._console = module.get_bin_path('console', False)

        self.command = module.params.get("command")
        self.working_dir = module.params.get("working_dir")
        self.runners = module.params.get("runners")

        self.forgejo_runner_bin = module.get_bin_path('forgejo-runner', True)

    def run(self):
        """
        """
        if not os.path.exists(self.working_dir):
            return dict(
                failed=True,
                changed=False,
                msg=f"missing directory {self.working_dir}"
            )

        if self.command == "create_runner":
            result = self.create_runner()

        return result

    def create_runner(self):
        """
            forgejo-runner create-runner-file --secret <secret>
        """
        os.chdir(self.working_dir)

        runner_name = socket.gethostname()

        self.module.log(msg=f"runners     : {self.runners}")
        self.module.log(msg=f"runner name : {runner_name}")

        know_runners = [x.get("name") for x in self.runners if x.get("name")]
        thats_me = next((x for x in self.runners if x.get("name") == runner_name), None)

        if not thats_me:
            known_runners = ",".join(know_runners)

            return dict(
                failed=True,
                msg=f"I can't find the runner with the name '{runner_name}'.\n"
                    f"I know the following runners: '{known_runners}'"
            )

        # self.module.log(msg=f"me : {thats_me[0]}")

        runner_secret = thats_me.get("secret", None)
        instance = thats_me.get("instance", None)

        args_list = [
            self.forgejo_runner_bin,
            "create-runner-file",
            "--secret", runner_secret,
            "--instance", instance,
            "--name", runner_name,
        ]

        rc, out, err = self._exec(args_list)

        if rc == 0:
            return dict(
                failed=False,
                changed=True,
                msg=f"Runner {runner_name} succesfully registerd."
            )
        else:
            return dict(
                failed=True,
                changed=False,
                msg=err.strip()
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
            default="create_runner",
            choices=[
                "create_runner",
            ]
        ),
        runners=dict(
            required=True,
            type=list,
            elements=dict
        ),
        working_dir=dict(
            required=True,
            type=str
        ),
    )

    module = AnsibleModule(
        argument_spec=specs,
        supports_check_mode=False,
    )

    kc = ForgejoRunner(module)
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
