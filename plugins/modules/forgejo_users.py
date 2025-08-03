#!/usr/bin/python
# -*- coding: utf-8 -*-

# (c) 2023, Bodo Schulz <bodo@boone-schulz.de>
# Apache (see LICENSE or https://opensource.org/licenses/Apache-2.0)

from __future__ import absolute_import, print_function

from ansible.module_utils.basic import AnsibleModule
from ansible_collections.bodsch.scm.plugins.module_utils.forgejo.api import ForgejoApi
from ansible_collections.bodsch.scm.plugins.module_utils.forgejo.users import ForgejoApiUsers
from ansible_collections.bodsch.scm.plugins.module_utils.forgejo.utils import validate_users, check_existing_users

from ansible_collections.bodsch.core.plugins.module_utils.module_results import results

__metaclass__ = type

DOCUMENTATION = r"""
---
module: forgejo_user
author: Bodo 'bodsch' Schulz <bodo@boone-schulz.de>
version_added: 1.0.0

short_description: Manage Forgejo users
description:
  - This module allows you to manage users in a Forgejo instance via its REST API.
  - You can list existing users, check if a specific user exists, create new users, and delete users.

options:
  users:
    description:
      - A list of users to manage. Each user is a dictionary with keys like
        C(username), C(password), C(email), and optionally C(state).
    required: true
    type: list

  server:
    description:
      - The base URL of the Forgejo instance.
    required: false
    default: http://localhost:3000
    type: str

  api_user:
    description:
      - Username for Forgejo API authentication.
    required: false
    type: str

  api_password:
    description:
      - Password for Forgejo API authentication.
    required: false
    type: str
    no_log: true
"""

EXAMPLES = r"""
- name: List all users in Forgejo
  bodsch.scm.forgejo_user:
    server: http://forgejo.local:3000
    api_user: admin
    api_password: secret
    users: []
  register: result

- name: Create a new user
  bodsch.scm.forgejo_user:
    server: http://forgejo.local:3000
    api_user: admin
    api_password: secret
    users:
      - username: "jdoe"
        password: "securePassw0rd!"
        email: "jdoe@example.com"
        state: present

- name: Delete a user
  bodsch.scm.forgejo_user:
    server: http://forgejo.local:3000
    api_user: admin
    api_password: secret
    users:
      - username: "olduser"
        state: absent
"""

RETURN = r"""
state:
  description: Detailed result for each processed user.
  returned: always
  type: list
  sample:
    - jdoe:
        failed: false
        changed: true
        msg: The user has been successfully created.

changed:
  description: Indicates if any user was created or deleted.
  returned: always
  type: bool

failed:
  description: Indicates if the module execution failed.
  returned: always
  type: bool
"""

# ----------------------------------------------------------------------


class ForgejoUsers:
    """
    """
    module = None

    def __init__(self, module):
        """
        """
        self.module = module

        self.users = module.params.get("users")
        self.server = module.params.get("server")
        self.api_user = module.params.get("api_user")
        self.api_password = module.params.get("api_password")

        api = ForgejoApi(
            module=self.module,
            base_url=f"{self.server}/api/v1",
            username=self.api_user,
            password=self.api_password
            # token="DEIN_TOKEN"  # optional
        )

        self.users_api = ForgejoApiUsers(api)

    def run(self):
        """
        """
        result = dict(
            changed=False,
            failed=True
        )
        result_state = []

        status_code, existing_users = self.users_api.list_users()

        valid_users, invalid_users = validate_users(users=self.users)
        _existing_users, non_existing_users = check_existing_users(new_users=valid_users, existing=existing_users)

        if len(invalid_users) > 0:
            result_state.append({
                "invalid users": {
                    "failed": True,
                    "changed": False,
                    "usernames": ", ".join([x.get("username") for x in invalid_users])
                }
            })

        for user in _existing_users:
            """
            """
            user_state = user.get("state", "present")
            user_name = user.get("username")

            res = {}

            if user_state == "absent":
                """
                    Delete users
                """
                status_code, _result = self.users_api.delete_user(
                    username=user_name
                )

                if status_code == 204:

                    res[user_name] = {
                        "failed": False,
                        "changed": True,
                        "msg": "The user has been successfully deleted."
                    }

                result_state.append(res)

        for user in non_existing_users:
            """
            """
            user_state = user.get("state", "present")
            user_name = user.get("username")
            user_password = user.get("password")
            user_email = user.get("email")

            res = {}

            if user_state == "present":

                status_code, _result = self.users_api.create_user(
                    username=user_name,
                    password=user_password,
                    email=user_email
                )

                if status_code == 201:

                    res[user_name] = {
                        "failed": False,
                        "changed": True,
                        "msg": "The user has been successfully created."
                    }

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
        server=dict(
            required=False,
            default="http://localhost:3000",
            type=str
        ),
        api_user=dict(
            required=False,
            type=str
        ),
        api_password=dict(
            required=False,
            type=str,
            no_log=True
        )
    )

    module = AnsibleModule(
        argument_spec=specs,
        supports_check_mode=False,
    )

    m = ForgejoUsers(module)
    result = m.run()

    # module.log(msg=f"= result : '{result}'")

    module.exit_json(**result)


# import module snippets
if __name__ == '__main__':
    main()
