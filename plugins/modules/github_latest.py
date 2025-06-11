#!/usr/bin/python3
# -*- coding: utf-8 -*-

# (c) 2022-2023, Bodo Schulz <bodo@boone-schulz.de>
# Apache-2.0 (see LICENSE or https://opensource.org/license/apache-2-0)
# SPDX-License-Identifier: Apache-2.0

from __future__ import absolute_import, print_function

import re
from pathlib import Path

from ansible.module_utils.basic import AnsibleModule
from ansible_collections.bodsch.core.plugins.module_utils.directory import create_directory

from ansible_collections.bodsch.scm.plugins.module_utils.github import GitHub

__metaclass__ = type

DOCUMENTATION = r"""
---
module: github_latest
author: Bodo 'bodsch' Schulz <bodo@boone-schulz.de>
version_added: 0.9.0

short_description: Fetches the latest version of a GitHub project and returns it.
description:
    - Fetches the latest version of a GitHub project and returns it.

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
  github_releases:
    description:
      - Searches for the last published Git release
    type: bool
    default: true
    required: false
  github_tags:
    description:
      - Search for the last published Git Tag
    type: bool
    default: false
    required: false
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
  without_beta:
    description:
      - Removes possible beta versions from the results.
    type: bool
    default: true
    required: false
  only_version:
    description:
      - returns only Versionnumbers without leading 'v' or 'V'
    type: bool
    default: true
    required: false
  filter_elements:
    description:
      - defined a list for a filter.
      - all hits are excluded from the final result
    type: list
    required: false
    default: []
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
  github_latest:
    project: prometheus
    repository: alertmanager
    user: "{{ lookup('env', 'GH_USER') | default(omit) }}"
    password: "{{ lookup('env', 'GH_TOKEN') | default(omit) }}"
  register: _latest_release

- name: get latest tag
  delegate_to: localhost
  become: false
  run_once: true
  github_latest:
    project: aws
    repository: aws-cli
    github_tags: true
    user: "{{ lookup('env', 'GH_USER') | default(omit) }}"
    password: "{{ lookup('env', 'GH_TOKEN') | default(omit) }}"
  register: _latest_release

- name: get latest tag without beta, preview or others
  delegate_to: localhost
  become: false
  run_once: true
  github_latest:
    project: aws
    repository: aws-cli
    github_tags: true
    user: "{{ lookup('env', 'GH_USER') | default(omit) }}"
    password: "{{ lookup('env', 'GH_TOKEN') | default(omit) }}"
    filter_elements:
      - ".*preview"
      - ".*beta"
      - ".*rc"
  register: _latest_release
"""

RETURN = r"""
failed:
    type: bool
    description:
        - True if an error occurs
latest_release:
    type: string
    description:
        - The last available version
"""


class GithubLatest(object):
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
        self.major_version = module.params.get("major_version")
        self.without_beta = module.params.get("without_beta")
        self.only_version = module.params.get("only_version")
        self.cache_minutes = int(module.params.get("cache"))
        self.github_releases = module.params.get("github_releases")
        self.github_tags = module.params.get("github_tags")
        self.filter_elements = module.params.get("filter_elements")

        # self.github_url = f"https://api.github.com/repos/{self.project}/{self.repository}"
        self.github_url = f"https://github.com/{self.project}/{self.repository}"

        url_path = "releases"

        if self.github_tags:
            self.github_releases = False
            url_path = "tags"

        self.github_url = f"{self.github_url}/{url_path}"

        self.cache_directory = f"{Path.home()}/.ansible/cache/github/{self.project}"
        self.cache_file_name = f"{self.repository}_releases.json"

    def run(self):
        """
        """
        create_directory(self.cache_directory)

        gh = GitHub(self.module)
        gh.enable_cache(cache_dir=self.cache_directory, cache_file=self.cache_file_name)
        gh.authentication(username=self.github_username, password=self.github_password, token=self.github_password)

        gh_releases = gh.get_releases(self.github_url)
        gh_latest_release = gh.latest_published(gh_releases)

        if self.github_tags:
            latest_release = gh_latest_release.get("tag_name", None)
        else:
            latest_release = gh_latest_release.get("name", None)

            if latest_release:
                pattern = re.compile(r'^\s*(\d+(?:\.\d+){1,})')
                match = pattern.match(latest_release)
                if match:
                    latest_release = match.group(1)

        return dict(
            failed=False,
            latest_release=latest_release.lstrip("v")
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
        github_releases=dict(
            required=False,
            type=bool,
            default=True,
        ),
        github_tags=dict(
            required=False,
            type=bool,
            default=False,
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
        major_version=dict(
            required=False,
        ),
        without_beta=dict(
            required=False,
            type=bool,
            default=True
        ),
        filter_elements=dict(
            required=False,
            type=list,
            default=[]
        ),
        only_version=dict(
            required=False,
            type=bool,
            default=True
        ),
        cache=dict(
            required=False,
            default=60
        )
    )

    module = AnsibleModule(
        argument_spec=args,
        supports_check_mode=False,
    )

    api = GithubLatest(module)
    result = api.run()

    # module.log(msg=f"= result : {result}")

    module.exit_json(**result)


# import module snippets
if __name__ == '__main__':
    main()
