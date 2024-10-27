#!/usr/bin/python
# -*- coding: utf-8 -*-

# (c) 2023, Bodo Schulz <bodo@boone-schulz.de>
# Apache (see LICENSE or https://opensource.org/licenses/Apache-2.0)

from __future__ import absolute_import, print_function
import os
import re

from ansible.module_utils.basic import AnsibleModule


__metaclass__ = type

ANSIBLE_METADATA = {
    'metadata_version': '0.1',
    'status': ['preview'],
    'supported_by': 'community'
}


class ForgejoUser(object):
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

        self.forgejo_bin = module.get_bin_path('forgejo', True)

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

        if self.state == "list":
            result = dict(
                changed=False,
                failed=False,
                msg=existing_users
            )

        if self.state == "check":
            if not existing_users.get(self.username):
                result = dict(
                    changed=False,
                    failed=False,
                    msg=f"User {self.username} is not created.",
                    rc=1
                )
            else:
                result = dict(
                    changed=False,
                    failed=False,
                    msg=f"User {self.username} is present.",
                    rc=0
                )

        if self.state == "present":
            if not existing_users.get(self.username):
                result = self.add_user()
            else:
                result = dict(
                    changed=False,
                    msg=f"user {self.username} already created."
                )

        if self.state == "absent":
            result["msg"] = "This part is currently not supported."

        return result

    def list_users(self):
        """
        """
        result = {}

        args_list = [
            self.forgejo_bin,
            "admin",
            "user",
            "list",
            "--work-path", self.working_dir,
            "--config", self.config,
        ]

        # self.module.log(msg=f"  args_list : '{args_list}'")
        rc, out, err = self._exec(args_list)

        outer_pattern = re.compile(r".*ID\s+Username\s+Email\s+IsActive\s+IsAdmin\s+2FA\n(?P<data>.*)", flags=re.MULTILINE | re.DOTALL)
        inner_pattern = re.compile(r"(?P<ID>\d+)\s+(?P<username>\w+)\s+(?P<email>[a-zA-Z+_\-@\.]+)\s+(?P<active>\w+)\s+(?P<admin>\w+)\s+(?P<twofa>\w+)", flags=re.MULTILINE | re.DOTALL)
        outer_re_result = re.search(outer_pattern, out)

        if outer_re_result:
            data = outer_re_result.group("data")
            inner_re_result = re.finditer(inner_pattern, data)

            if inner_re_result:
                for x in inner_re_result:
                    if x.group("username"):
                        username = x.group("username")

                    if x.group("email"):
                        email = x.group("email")
                    else:
                        email = "unknown"

                    if x.group("active"):
                        active = bool(x.group("active"))
                    else:
                        active = False

                    if x.group("admin"):
                        admin = bool(x.group("admin"))
                    else:
                        admin = False

                    result[str(username)] = dict(
                        email=email,
                        active=active,
                        admin=admin
                    )

        return result

    def add_user(self):
        """
            forgejo admin user create --admin --username root --password admin1234 --email root@example.com
        """
        args_list = [
            self.forgejo_bin,
            "admin",
            "user",
            "create",
            "--work-path", self.working_dir,
            "--config", self.config,
        ]

        if self.admin:
            args_list.append("--admin")

        args_list += [
            "--username", self.username,
            "--password", self.password,
            "--email", self.email
        ]

        # self.module.log(msg=f"  args_list : '{args_list}'")

        rc, out, err = self._exec(args_list)

        if rc == 0:
            return dict(
                failed=False,
                changed=True,
                msg=f"user {self.username} successful created."
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
        state=dict(
            default="present",
            choices=[
                "present",
                "absent",
                "list",
                "check"
            ]
        ),
        admin=dict(
            required=False,
            type=bool,
            default=False
        ),
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

    params = module.params

    _state = params.get("state")

    if _state in ["present", "absent", "check"]:

        res_args = dict(
            rc=1,
            changed=False
        )
        _username = params.get("username", None)
        _password = params.get("password", None)
        _email = params.get("email", None)

        if _state == "present":
            _missing = []
            if _username is None:
                _missing.append("username")
            if _password is None:
                _missing.append("password")
            if _email is None:
                _missing.append("email")

            if len(_missing) > 0:
                _missing = ", ".join(_missing)
                res_args['msg'] = f"missing required arguments: {_missing}"
                module.exit_json(**res_args)

        if _state in ["absent", "check"]:
            if _username is None:
                res_args['msg'] = "missing required arguments: username"
                module.exit_json(**res_args)

    kc = ForgejoUser(module)
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
