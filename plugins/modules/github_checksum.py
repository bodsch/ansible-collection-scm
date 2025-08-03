#!/usr/bin/python3
# -*- coding: utf-8 -*-

from __future__ import absolute_import, print_function
import os
from enum import Enum
from pathlib import Path

from ansible.module_utils.basic import AnsibleModule

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
  - This module fetches checksum information of a release asset from a GitHub repository.
  - It supports caching to minimize requests to GitHub and reduce the risk of rate limiting.
  - The module returns the single matching checksum as well as a list of all available checksums.

options:
  project:
    description:
      - Defines the GitHub project (organization or user).
      - "Example: **prometheus**/alertmanager → project = prometheus"
    required: true
    type: str
  repository:
    description:
      - Defines the repository name within the given project.
      - "Example: prometheus/**alertmanager** → repository = alertmanager"
    required: true
    type: str
  architecture:
    description:
      - Target architecture used to filter the checksums.
      - Valid values correspond to common system architectures.
    required: false
    type: str
    default: x86_64
  system:
    description:
      - Target operating system used to filter the checksums.
    required: false
    type: str
    default: Linux
  checksum_file:
    description:
      - The name of the checksum file to fetch from the GitHub release assets.
    required: false
    type: str
    default: checksums.txt
  version:
    description:
      - GitHub release version (tag) to look up.
      - Must match an existing release tag in the repository.
    required: true
    type: str
  user:
    description:
      - Optional GitHub username for authentication.
    required: false
    type: str
  password:
    description:
      - Optional GitHub personal access token or password.
      - Used to avoid rate limiting or access private repositories.
    required: false
    type: str
  cache:
    description:
      - Validity of cached metadata in seconds.
      - Prevents unnecessary repeated GitHub API calls.
    required: false
    type: int
    default: 60
'''

EXAMPLES = r"""
- name: Get checksum list for a GitHub release
  bodsch.scm.github_latest:
    project: prometheus
    repository: alertmanager
    version: "v0.25.0"
    checksum_file: sha256sums.txt
    user: "{{ lookup('env', 'GH_USER') | default(omit) }}"
    password: "{{ lookup('env', 'GH_TOKEN') | default(omit) }}"
    architecture: "{{ ansible_architecture }}"
    system: "{{ ansible_facts.system }}"
  register: github_release_checksums

- name: Show the fetched checksum
  debug:
    msg: "The checksum is {{ github_release_checksums.checksum }}"

- name: Use all checksums in a loop
  debug:
    msg: "Found checksum {{ item }}"
  loop: "{{ github_release_checksums.checksums }}"
"""

RETURN = r"""
failed:
  description:
    - Indicates whether the module execution failed.
  type: bool
  returned: always
rc:
  description:
    - Return code of the operation.
    - 0 indicates success; non-zero indicates a problem retrieving the checksum.
  type: int
  returned: always
checksum:
  description:
    - The single checksum matching the requested architecture and system.
  type: str
  returned: success
  sample: "abc123def456..."
checksums:
  description:
    - List of all checksums found in the checksum file for the given release.
  type: list
  elements: str
  returned: success
  sample:
    - "abc123def456..."
    - "789ghi012jkl..."
msg:
  description:
    - Error message if the module fails to fetch the checksum.
  type: str
  returned: on failure
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

        release = gh.release_exists(tag=self.version)

        if len(release) == 0:
            return dict(
                failed=True,
                checksum=None,
                checksums=[],
                msg=f"An error has occurred. Please check the availability of {self.project}/{self.repository} and version {self.version} at Github!"
            )

        gh_checksum_data = gh.get_checksum_asset(tag=self.version)

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
