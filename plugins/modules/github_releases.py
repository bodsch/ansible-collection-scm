#!/usr/bin/python3
# -*- coding: utf-8 -*-

# (c) 2022-2023, Bodo Schulz <bodo@boone-schulz.de>
# Apache-2.0 (see LICENSE or https://opensource.org/license/apache-2-0)
# SPDX-License-Identifier: Apache-2.0

from __future__ import absolute_import, print_function
# import urllib3
# import requests
# import json
# import os
import re
from enum import Enum
from pathlib import Path

from ansible.module_utils.basic import AnsibleModule
# from ansible_collections.bodsch.core.plugins.module_utils.cache.cache_valid import cache_valid
from ansible_collections.bodsch.core.plugins.module_utils.directory import create_directory

from ansible_collections.bodsch.scm.plugins.module_utils.github import GitHub

__metaclass__ = type

DOCUMENTATION = r"""
---
module: github_releases
author: Bodo 'bodsch' Schulz <bodo@boone-schulz.de>
version_added: 0.9.6

short_description: Fetches the releases version of a GitHub project and returns the download urls.
description:
    - Fetches the releases version of a GitHub project and returns the download urls.

options:
  project:
    description:
      - Defines the project in which a repository has been created.
      - "For example: **prometheus**/alertmanager"
    type: str
    required: true

  repository:
    description:
      - Defines the repository that is maintained underneath a project.
      - "For example: prometheus/**alertmanager**"
    type: str
    required: true

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

  version:
    required: true
    description: TODO
    type: str

  user:
    description:
      - GitHub Username
    type: str
    required: false

  password:
    description:
      - GitHub Passwort
    type: str
    required: false

  cache:
    description:
      - Defines the validity of the meta information in seconds.
      - If this expires, the meta information is reloaded from GitHub.
      - This is to prevent the rate limit from being used unnecessarily.
    type: int
    default: 60
    required: false
"""

EXAMPLES = r"""
- name: get latest release
  delegate_to: localhost
  become: false
  run_once: true
  bodsch.scm.github_releases:
    project: prometheus
    repository: alertmanager
    version: "{{ alertmanager_version }}"
    architecture: "{{ ansible_architecture }}"
    system: "{{ ansible_facts.system }}"
    user: "{{ lookup('env', 'GH_USER') | default(omit) }}"
    password: "{{ lookup('env', 'GH_TOKEN') | default(omit) }}"
  register: _glauth_releases
  until: _glauth_releases.status == 200
  retries: 2
"""

RETURN = r"""
download_url:
    type: str
    description:
        - The Download URL for the release artefact, based on version, system and architecture
urls:
    type: list
    description:
        - A full list of all artefacts
status:
    type: int
    description:
        - HTTP result code
"""


class Architecture(Enum):
    amd64 = "x86_64"
    arm64 = "aarch64"
    armv7 = "armv7l"
    armv6 = "armv6l"


class GithubReleases(object):
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
        self.version = module.params.get("version")
        self.architecture = Architecture(module.params.get("architecture")).name
        self.system = module.params.get("system").lower()
        self.cache_minutes = int(module.params.get("cache"))

        self.github_url = f"https://github.com/{self.project}/{self.repository}"

        self.cache_directory = f"{Path.home()}/.ansible/cache/github/{self.project}"

    def run(self):
        """
        """
        create_directory(self.cache_directory)

        gh = GitHub(self.module)
        gh.architecture(system=self.system, architecture=self.architecture)
        gh.enable_cache(cache_dir=self.cache_directory)

        gh.authentication(username=self.github_username, password=self.github_password, token=self.github_password)

        gh_result = gh.get_all_releases(repo_url=self.github_url)

        if gh_result:
            if isinstance(gh_result, list):
                download_urls = [x.get("download_urls") for x in gh_result if x.get("name").lstrip("v") == self.version.lstrip("v")]

                try:
                    if len(download_urls) > 0:
                        download_urls = download_urls[0]

                        matches = [
                            x for x in download_urls
                            if re.search(fr".*{self.version.lstrip('v')}.*{self.system}.*{self.architecture}.*", x)
                        ]

                        # contains_list = any(isinstance(item, list) for item in download_urls)
                        if matches:
                            download_url = matches[0]

                            return dict(
                                status=200,
                                urls=download_urls,
                                download_url=download_url
                            )
                        else:
                            return dict(
                                status=500,
                                msg="No matching download URL found."
                            )

                except Exception as e:
                    self.module.log(msg=f"E: {e}")
                    pass

        return dict(
            status=500,
            msg=f"No release information could be found under {self.github_url}.",
        )


def main():
    """
    """
    args = dict(
        project=dict(
            required=True,
            type=str
        ),
        repository=dict(
            required=True,
            type=str
        ),
        version=dict(
            required=True,
            type=str,
        ),
        architecture=dict(
            required=False,
            type=str,
            default="x86_64",
        ),
        system=dict(
            required=False,
            type=str,
            default="Linux",
        ),
        user=dict(
            required=False,
            type=str
        ),
        password=dict(
            required=False,
            type=str,
            no_log=True
        ),
        cache=dict(
            required=False,
            default=120
        )
    )

    module = AnsibleModule(
        argument_spec=args,
        supports_check_mode=False,
    )

    api = GithubReleases(module)
    result = api.run()

    module.log(msg=f"= result : {result}")

    module.exit_json(**result)


# import module snippets
if __name__ == '__main__':
    main()
