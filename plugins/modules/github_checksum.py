#!/usr/bin/python3
# -*- coding: utf-8 -*-

from __future__ import absolute_import, print_function
# import urllib3
import os
from enum import Enum
from pathlib import Path

from ansible.module_utils.basic import AnsibleModule
# from ansible_collections.bodsch.core.plugins.module_utils.directory import create_directory

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
        # self.github_url = f"https://github.com/{self.project}/{self.repository}/releases/download"

        self.cache_directory = f"{Path.home()}/.cache/ansible/github/{self.project}/{self.repository}"
        self.cache_file_name = f"{self.version}_{self.checksum_file}"

        # urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

    def run(self):
        """
        """
        rc = 10

        # create_directory(self.cache_directory)
        gh_authentication = dict(
            token=self.github_password
        )

        gh = GitHub(self.module, owner=self.project, repository=self.repository, auth=gh_authentication)
        gh.architecture(system=self.system, architecture=self.architecture)
        gh.enable_cache(cache_minutes=self.cache_minutes)

        release = gh.release_exists(repo_url=f"https://github.com/{self.project}/{self.repository}", tag=self.version)

        if len(release) == 0:
            return dict(
                failed=True,
                checksum=None,
                checksums=[],
                msg=f"An error has occurred. Please check the availability of {self.project}/{self.repository} and version {self.version} at Github!"
            )

        gh_checksum_data = gh.get_checksum_asset(owner=self.project, repo=self.repository, tag=self.version)

        cache_file_name = os.path.join(self.cache_directory, f"{self.cache_file_name}")

        if gh_checksum_data:
            url = gh_checksum_data.get("url")
            gh.download_checksum(url, filename=cache_file_name)

        data, gh_checksum = gh.checksum(repo=self.repository, filename=cache_file_name)

        if len(gh_checksum) > 0:
            rc = 0

        return dict(
            failed=False,
            rc=rc,
            checksum=gh_checksum,
            checksums=data
        )


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

    # module.log(msg=f"= result : {result}")

    module.exit_json(**result)


# import module snippets
if __name__ == '__main__':
    main()
