#!/usr/bin/python3
# -*- coding: utf-8 -*-

from __future__ import absolute_import, print_function
import urllib3
import requests
import json
import os
import re
from enum import Enum

from packaging.version import parse as parseVersion
from pathlib import Path

from ansible.module_utils.basic import AnsibleModule
from ansible_collections.bodsch.core.plugins.module_utils.cache.cache_valid import cache_valid
from ansible_collections.bodsch.core.plugins.module_utils.directory import create_directory

from ansible_collections.bodsch.scm.plugins.module_utils.github import GitHub

__metaclass__ = type

ANSIBLE_METADATA = {
    'metadata_version': '0.1',
    'status': ['preview'],
    'supported_by': 'community'
}

DOCUMENTATION = r'''
---
module: github_latest
author: Bodo 'bodsch' Schulz <bodo@boone-schulz.de>
version_added: 0.9.0

short_description: Fetches a checksum of a GitHub project and returns it.
description:
    - Fetches a checksum of a GitHub project and returns it.

options:
  project:
    required: true
    description:
      - Defines the project in which a repository has been created.
      - "For example: **prometheus**/alertmanager"
    type: str
  repository:
    required: true
    description:
      - Defines the repository that is maintained underneath a project.
      - "For example: prometheus/**alertmanager**"
    type: str

  architecture:
    required: false
    description: TODO
    type: str
    default: x86_64

  system:
    required: false
    description: TODO
    type: str
    default: Linux

  checksum_file:
    required: false
    description: TODO
    type: str
    default: checksums.txt

  version:
    required: true
    description: TODO
    type: str

  user:
    required: false
    description:
      - GitHub Username
    type: str
  password:
    required: false
    description:
      - GitHub Passwort
    type: str
  cache:
    required: false
    description:
      - Defines the validity of the meta information in seconds.
      - If this expires, the meta information is reloaded from GitHub.
      - This is to prevent the rate limit from being used unnecessarily.
    type: int
    default: 60
'''

EXAMPLES = r"""
- name: get checksum list
  github_checksum:
    project: prometheus
    repository: alertmanager
    checksum_file: sha256sums.txt
    user: "{{ lookup('env', 'GH_USER') | default(omit) }}"
    password: "{{ lookup('env', 'GH_TOKEN') | default(omit) }}"
    architecture: "{{ ansible_architecture }}"
    system: "{{ ansible_facts.system }}"
    version: "v0.10.0"
  register: _latest_checksum
"""

RETURN = r"""
failed:
    type: bool
    description:
        - True if an error occurs
rc:
    type: int
    description:
        - return code
        - 0 means are all okay
checksum:
    type: string
    description: the checksum
checksums:
    type: list
    description: a list with all checksums
"""


class Architecture(Enum):
    amd64 = "x86_64"
    arm64 = "aarch64"
    armv7 = "armv7l"
    armv6 = "armv6l"


class GithubChecksum(object):
    """
    Main Class
    """
    module = None

    def __init__(self, module):
        """
          Initialize all needed Variables
        """
        self.module = module

        self.project = module.params.get("project")
        self.repository = module.params.get("repository")
        self.github_username = module.params.get("user")
        self.github_password = module.params.get("password")
        # self.github_token = module.params.get("token")
        self.architecture = Architecture(module.params.get("architecture")).name
        self.system = module.params.get("system").lower()
        self.checksum_file = module.params.get("checksum_file")
        self.version = module.params.get("version")
        self.cache_minutes = int(module.params.get("cache"))

        # https://github.com/prometheus/alertmanager/releases/download/v0.25.0/sha256sums.txt
        self.github_url = f"https://github.com/{self.project}/{self.repository}/releases/download"

        self.cache_directory = f"{Path.home()}/.ansible/cache/github/{self.project}/{self.repository}"
        self.cache_file_name = os.path.join(self.cache_directory, f"{self.version}_{self.checksum_file}")

        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

    def run(self):
        """
        """
        checksum = None
        rc = 10

        create_directory(self.cache_directory)

        gh = GitHub(self.module)
        gh.authentication(username=self.github_username, password=self.github_password, token=self.github_password)
        gh_result = gh.get_releases(repo_url=f"https://github.com/{self.project}/{self.repository}")

        self.module.log(msg=f" -> {gh_result}")


        status, data = self.latest_information()

        self.module.log(msg=f"data: {data} {type(data)} {len(data)}")
        self.module.log(msg=f"  - {self.repository}")
        self.module.log(msg=f"  - {self.system}")
        self.module.log(msg=f"  - {self.architecture}")

        if status != 200:
            return dict(
                failed=True,
                checksum=None,
                checksums=[],
                msg=f"An error has occurred. Please check the availability of {self.project}/{self.repository} and version {self.version} at Github!"
            )

        # e9fa07f094b8efa3f1f209dc7d51a7cf428574906c7fd8eac9a3aed08b03ed63  alertmanager-0.25.0.darwin-amd64.tar.gz
        checksum = [x for x in data if re.search(fr".*{self.repository}.*{self.system}.*{self.architecture}.*", x)]

        if isinstance(checksum, list) and len(checksum) == 1:
            checksum = checksum[0]
        else:
            if isinstance(data, list) and len(data) == 1:
                """
                    single entry
                """
                _chk = data[0].split(" ")
                _len = len(_chk)

                if _len == 1:
                    checksum = _chk[0]

        if isinstance(checksum, str):
            checksum = checksum.split(" ")[0]

        if len(checksum) > 0:
            rc = 0

        return dict(
            failed=False,
            rc=rc,
            checksum=checksum,
            checksums=data
        )

    def latest_information(self):
        """
        """
        output = None

        out_of_cache = cache_valid(self.module, self.cache_file_name, self.cache_minutes, True)

        if not out_of_cache:
            with open(self.cache_file_name, "r") as f:
                output = json.loads(f.read())

                return output

        if not output:
            self.module.log(msg=f" - read from url  {self.github_url}")

            status_code, output = self.__call_url()

            self.module.log(msg=f" - output  {output} {type(output)}")
            # convert the strings into a list
            output = output.split("\n")
            # and remove empty elements
            output[:] = [x for x in output if x]

            self.module.log(msg=f" - output  {output} {type(output)}")

            if status_code == 200:
                self.save_latest_information(output)

                return status_code, output
            else:
                return status_code, []

    def save_latest_information(self, data):
        """
        """
        with open(self.cache_file_name, "w") as f:
            json.dump(data, f, indent=2, sort_keys=True)

    def __call_url(self, method='GET', data=None):
        """
        """
        self.module.log(msg=f"GithubChecksum::__call_url({method}, {data})")

        response = None

        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json;charset=utf-8"
        }

        github_url = f"{self.github_url}/{self.version}/{self.checksum_file}"
        self.module.log(msg=f"  url  {github_url}")

        try:
            authentication = (self.github_username, self.github_password)

            if method == "GET":
                response = requests.get(
                    github_url,
                    headers=headers,
                    auth=authentication
                )

            else:
                print("unsupported")
                pass

            response.raise_for_status()

            self.module.log(msg=f" text    : {response.text} / {type(response.text)}")
            # self.module.log(msg=f" json    : {response.json()} / {type(response.json())}")
            self.module.log(msg=f" headers : {response.headers}")
            self.module.log(msg=f" code    : {response.status_code}")
            self.module.log(msg="------------------------------------------------------------------")

            return response.status_code, response.text

        except requests.exceptions.HTTPError as e:
            self.module.log(msg=f"ERROR   : {e}")

            status_code = e.response.status_code
            status_message = e.response.text
            # self.module.log(msg=f" status_message : {status_message} / {type(status_message)}")
            # self.module.log(msg=f" status_message : {e.response.json()}")

            return status_code, status_message

        except ConnectionError as e:
            error_text = f"{type(e).__name__} {(str(e) if len(e.args) == 0 else str(e.args[0]))}"
            self.module.log(msg=f"ERROR   : {error_text}")

            self.module.log(msg="------------------------------------------------------------------")
            return 500, error_text

        except Exception as e:
            self.module.log(msg=f"ERROR   : {e}")
            # self.module.log(msg=f" text    : {response.text} / {type(response.text)}")
            # self.module.log(msg=f" json    : {response.json()} / {type(response.json())}")
            # self.module.log(msg=f" headers : {response.headers}")
            # self.module.log(msg=f" code    : {response.status_code}")
            # self.module.log(msg="------------------------------------------------------------------")

            return response.status_code, response.text

    def version_sort(self, version_list):
        """
        """
        version_list.sort(key=parseVersion)

        return version_list


def main():
    """
    """
    argument_spec = dict(
        project=dict(
            type=str,
            required=True,
        ),
        repository=dict(
            type=str,
            required=True,
        ),
        architecture=dict(
            type=str,
            required=False,
            default="x86_64",
        ),
        system=dict(
            type=str,
            required=False,
            default="Linux",
        ),
        checksum_file=dict(
            type=str,
            required=False,
            default="checksums.txt",
        ),
        user=dict(
            type=str,
            required=False,
        ),
        password=dict(
            type=str,
            required=False,
            no_log=True
        ),
        version=dict(
            type=str,
            required=True,
        ),
        cache=dict(
            type=int,
            required=False,
            default=60
        )
    )

    module = AnsibleModule(
        argument_spec=argument_spec,
        supports_check_mode=False,
    )

    api = GithubChecksum(module)
    result = api.run()

    module.log(msg=f"= result : {result}")

    module.exit_json(**result)


# import module snippets
if __name__ == '__main__':
    main()
