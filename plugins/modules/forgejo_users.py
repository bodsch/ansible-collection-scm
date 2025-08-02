#!/usr/bin/python
# -*- coding: utf-8 -*-

# (c) 2023, Bodo Schulz <bodo@boone-schulz.de>
# Apache (see LICENSE or https://opensource.org/licenses/Apache-2.0)

from __future__ import absolute_import, print_function

from ansible.module_utils.basic import AnsibleModule
from ansible_collections.bodsch.scm.plugins.module_utils.forgejo.api import ForgejoApi
from ansible_collections.bodsch.scm.plugins.module_utils.forgejo.users import ForgejoUsers as ForgejoApiUsers
from ansible_collections.bodsch.scm.plugins.module_utils.forgejo.utils import validate_users, check_existing_users

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

        # self.module.log(msg=f"existing_users: {existing_users}")
        # self.module.log(msg=f"valid_users: {valid_users}")
        # self.module.log(msg=f"invalid_users: {invalid_users}")
        # self.module.log(msg=f"_existing_users: {_existing_users}")
        # self.module.log(msg=f"non_existing_users: {non_existing_users}")

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

                # self.module.log(msg=f"  - : {status_code} {_result}")

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

                # self.module.log(msg=f"  - : {status_code} {_result}")
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
