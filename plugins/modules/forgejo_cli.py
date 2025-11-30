#!/usr/bin/python
# -*- coding: utf-8 -*-

# (c) 2023, Bodo Schulz <bodo@boone-schulz.de>
# Apache (see LICENSE or https://opensource.org/licenses/Apache-2.0)

from __future__ import absolute_import, print_function

from ansible.module_utils.basic import AnsibleModule
from ansible_collections.bodsch.core.plugins.module_utils.module_results import results

__metaclass__ = type

DOCUMENTATION = r"""
---
module: forgejo_cli
author: Bodo 'bodsch' Schulz <bodo@boone-schulz.de>
version_added: 1.0.0

short_description: Register Forgejo runners using the Forgejo CLI.
description:
  - This module allows registering Forgejo runners on a Forgejo server
    by invoking the Forgejo CLI.
  - It supports assigning runner secrets, scopes and labels.

options:
  command:
    description:
      - The operation to perform.
      - Currently only runner registration is supported.
    choices: ["register"]
    default: register
    type: str

  parameters:
    description:
      - Optional additional parameters (currently unused).
    required: false
    type: list
    default: []

  working_dir:
    description:
      - Working directory for Forgejo CLI commands.
      - This is usually the Forgejo data directory.
    required: true
    type: str

  config:
    description:
      - Path to the Forgejo configuration file.
    required: false
    type: str
    default: /etc/forgejo/forgejo.ini

  runners:
    description:
      - List of runners to register.
      - Each runner is a dictionary with at least C(name) and C(secret).
      - Optional keys: C(scope), C(labels) (list of labels).
    required: true
    type: list
"""

EXAMPLES = r"""
- name: create runner token on {{ forgejo_runner_controller.hostname }}
  remote_user: "{{ forgejo_runner_controller.remoteuser }}"
  become_user: "{{ forgejo_runner_controller.username }}"
  become: true
  delegate_to: "{{ forgejo_runner_controller.hostname }}"
  bodsch.scm.forgejo_cli:
    command: register
    config: "{{ forgejo_config_dir }}/forgejo.ini"
    working_dir: "{{ forgejo_working_dir }}"
    runners: "{{ forgejo_runner_register | default([]) }}"

- name: Register runners on Forgejo
  become: true
  remote_user: "{{ forgejo_runner_controller.remoteuser }}"
  become_user: "{{ forgejo_runner_controller.username }}"
  delegate_to: "{{ forgejo_runner_controller.hostname }}"
  bodsch.scm.forgejo_cli:
    command: register
    working_dir: "{{ forgejo_working_dir }}"
    config: "{{ forgejo_config_dir }}/forgejo.ini"
    runners:
      - name: runner1
        secret: "SECRET_TOKEN_1"
        scope: "instance"
        labels:
          - linux
          - x86
      - name: runner2
        secret: "SECRET_TOKEN_2"
"""

RETURN = r"""
changed:
  description: Indicates if any runner was successfully registered.
  returned: always
  type: bool

failed:
  description: True if any runner registration failed.
  returned: always
  type: bool

state:
  description: A list of results for each runner processed.
  returned: always
  type: list
  elements: dict
  sample:
    - runner1:
        failed: false
        msg: "Runner runner1 succesfully created."
    - runner2:
        failed: true
        msg: "Missing secret."

"""

# ----------------------------------------------------------------------


class ForgejoCli(object):
    """ """

    module = None

    def __init__(self, module):
        """ """
        self.module = module

        # self._console = module.get_bin_path('console', False)

        self.command = module.params.get("command")
        self.parameters = module.params.get("parameters")
        self.working_dir = module.params.get("working_dir")
        self.environment = module.params.get("environment")
        self.config = module.params.get("config")
        self.runners = module.params.get("runners")

        self.forgejo_bin = module.get_bin_path("forgejo", True)

    def run(self):
        """ """

        if self.command == "register":
            result = self.register()

        return result

    def register(self):
        """
        https://forgejo.org/docs/latest/admin/actions/#registration
        forgejo forgejo-cli actions register --secret <secret>

        forgejo action --help --config /etc/forgejo/forgejo.ini
        """

        result_state = []

        for runner in self.runners:
            res = {}
            self.module.log(msg=f"  - '{runner}' ({type(runner)})")

            runner_name = runner.get("name", None)

            self.module.log(msg=f"     '{runner_name}'")
            # runner_tags = []
            # runner_token = ""
            runner_secret = ""
            runner_scope = ""
            runner_labels = []

            if runner_name:
                # runner_tags = runner.get("tags", [None])
                # runner_token = runner.get("token", None)
                runner_secret = runner.get("secret", None)
                runner_scope = runner.get("scope", None)
                runner_labels = runner.get("labels", [])

                if not runner_secret:
                    res[runner_name] = dict(failed=True, msg="Missing secret.")
                else:
                    data = dict(
                        runner_secret=runner_secret,
                        runner_scope=runner_scope,
                        runner_labels=runner_labels,
                    )

                    rc, out, err = self.register_runner(runner_name, data=data)

                    if rc == 0:
                        res = dict(
                            failed=False,
                            msg=f"Runner {runner_name} succesfully created.",
                        )

                result_state.append(res)

        self.module.log(msg=f"= {result_state}")

        _state, _changed, _failed, state, changed, failed = results(
            self.module, result_state
        )

        result = dict(changed=_changed, failed=failed, state=result_state)

        return result

    def register_runner(self, runner_name, data):

        secret = data.get("runner_secret")
        scope = data.get("runner_scope", None)
        labels = data.get("runner_labels", [])

        args_list = [
            self.forgejo_bin,
            "--work-path",
            self.working_dir,
            "--config",
            self.config,
            "forgejo-cli",
            "actions",
            "register",
            "--name",
            runner_name,
            "--secret",
            secret,
        ]

        if scope:
            args_list.append(["--scope", scope])

        if isinstance(labels, list) and len(labels) > 0:
            _labels = ",".join(labels)
            args_list += ["--labels", _labels]

        self.module.log(msg=f"cmd: {args_list}")

        rc, out, err = self._exec(args_list, check_rc=False)

        self.module.log(msg=f"out: {out}")
        self.module.log(msg=f"err: {err}")
        self.module.log(msg=f"cmd: {args_list}")

        return rc, out, err

    def _exec(self, commands, check_rc=True):
        """ """
        rc, out, err = self.module.run_command(commands, check_rc=check_rc)

        self.module.log(msg=f"  rc : '{rc}'")

        # if rc != 0:
        self.module.log(msg=f"  out: '{out}'")
        self.module.log(msg=f"  err: '{err}'")

        return rc, out, err


def main():
    """ """
    specs = dict(
        command=dict(
            default="register",
            choices=[
                "register",
            ],
        ),
        parameters=dict(required=False, type=list, default=[]),
        working_dir=dict(required=True, type=str),
        config=dict(required=False, default="/etc/forgejo/forgejo.ini", type=str),
        runners=dict(
            required=True,
            type=list,
        ),
    )

    module = AnsibleModule(
        argument_spec=specs,
        supports_check_mode=False,
    )

    kc = ForgejoCli(module)
    result = kc.run()

    module.log(msg=f"= result : '{result}'")

    module.exit_json(**result)


# import module snippets
if __name__ == "__main__":
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
