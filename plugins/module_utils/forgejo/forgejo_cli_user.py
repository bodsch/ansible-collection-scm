
from __future__ import absolute_import, print_function
import re
from typing import Optional, List, Tuple


class ForgejoUser:
    """
    """
    module = None

    def __init__(self, module: any, working_dir: str, forgejo_config: str):
        """
        """
        self.module = module

        self.working_dir = working_dir
        self.config = forgejo_config

        self.forgejo_bin = module.get_bin_path('forgejo', True)

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

        pattern = re.compile(
            r'^\s*(?P<id>\d+)\s+'
            r'(?P<username>\S+)\s+'
            r'(?P<email>\S+)\s+'
            r'(?P<is_active>true|false)\s+'
            r'(?P<is_admin>true|false)\s+'
            r'(?P<two_fa>true|false)\s*$'
        )

        result = {
            m.group('username'): {
                'email': m.group('email'),
                'active': m.group('is_active') == 'true',
                'admin': m.group('is_admin') == 'true'
            }
            for line in out.splitlines()[1:]  # Zeile 1 ist der Header
            if (m := pattern.match(line))
        }

        return result

    def add_user(self, username: str, password: str, email: str, admin_user: Optional[bool] = False):
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

        if admin_user:
            args_list.append("--admin")

        args_list += [
            "--username", username,
            "--password", password,
            "--email", email
        ]

        # self.module.log(msg=f"  args_list : '{args_list}'")

        rc, out, err = self._exec(args_list)

        if rc == 0:
            return dict(
                failed=False,
                changed=True,
                msg=f"user {username} successful created."
            )
        else:
            return dict(
                failed=True,
                msg=err
            )

    def validate_users(self) -> Tuple[List[dict], List[dict]]:
        """
        """
        valid_users = []
        invalid_users = []

        for user in self.users:
            username = user.get('username', '').strip()
            password = user.get('password', '').strip()
            email = user.get('email', '').strip()

            # Prüfe Vollständigkeit und Eindeutigkeit
            if username and password and email:
                valid_users.append(user)
            else:
                invalid_users.append(user)

        return valid_users, invalid_users

    def check_existing_users(self, new_users: List[dict], existing: dict) -> Tuple[List[dict], List[dict]]:
        """
        """
        existing_usernames = {username.lower() for username in existing.keys()}
        existing_emails = {user.get('email').lower() for user in existing.values()}

        existing_users = []
        non_existing_users = []

        for user in new_users:
            username = user.get('username').lower()
            email = user.get('email').lower()

            if username in existing_usernames or email in existing_emails:
                existing_users.append(user)
            else:
                non_existing_users.append(user)
                existing_usernames.add(username)
                existing_emails.add(email)

        return existing_users, non_existing_users

    def _exec(self, commands, check_rc=True):
        """
        """
        rc, out, err = self.module.run_command(commands, check_rc=check_rc)
        # self.module.log(msg=f"  rc : '{rc}'")

        if rc != 0:
            self.module.log(msg=f"  out: '{out}'")
            self.module.log(msg=f"  err: '{err}'")

        return rc, out, err
