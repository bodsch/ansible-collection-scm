#!/usr/bin/python
# -*- coding: utf-8 -*-

# (c) 2023, Bodo Schulz <bodo@boone-schulz.de>
# Apache (see LICENSE or https://opensource.org/licenses/Apache-2.0)

from __future__ import absolute_import, print_function

from ansible.module_utils.basic import AnsibleModule


__metaclass__ = type

ANSIBLE_METADATA = {
    'metadata_version': '0.1',
    'status': ['preview'],
    'supported_by': 'community'
}


class GiteaCli(object):
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

        if self.state == "migrate":
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

        rc, out, err = self._exec(args_list)

    def add_user(self):
        """
            forgejo admin user create --admin --username root --password admin1234 --email root@example.com
        """

        args_list = [
            self.forgejo_bin,
            "--work-path", self.working_dir,
            "--config", self.config,
            "admin",
            "user",
            "create",

        ]

        rc, out, err = self._exec(args_list)

    def _exec(self, commands, check_rc=True):
        """
        """
        rc, out, err = self.module.run_command(commands, check_rc=check_rc)
        self.module.log(msg=f"  rc : '{rc}'")

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
            required=True,
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

    kc = GiteaCli(module)
    result = kc.run()

    module.log(msg=f"= result : '{result}'")

    module.exit_json(**result)


# import module snippets
if __name__ == '__main__':
    main()

"""
root@instance:/# forgejo --help
NAME:
   Gitea - A painless self-hosted Git service

USAGE:
   forgejo [global options] command [command options] [arguments...]

VERSION:
   1.19.0 built with GNU Make 4.1, go1.20.2 : bindata, sqlite, sqlite_unlock_notify

DESCRIPTION:
   By default, forgejo will start serving using the webserver with no
arguments - which can alternatively be run by running the subcommand web.

COMMANDS:
   web              Start Gitea web server
   serv             This command should only be called by SSH shell
   hook             Delegate commands to corresponding Git hooks
   dump             Dump Gitea files and database
   cert             Generate self-signed certificate
   admin            Command line interface to perform common administrative operations
   generate         Command line interface for running generators
   migrate          Migrate the database
   keys             This command queries the Gitea database to get the authorized command for a given ssh key fingerprint
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
