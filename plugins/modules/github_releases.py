#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# (c) 2022-2023, Bodo Schulz <bodo@boone-schulz.de>
# Apache-2.0 (see LICENSE or https://opensource.org/license/apache-2-0)
# SPDX-License-Identifier: Apache-2.0

from __future__ import absolute_import, print_function
import urllib3
import requests
import json
import os
import re
from enum import Enum
from pathlib import Path

from ansible.module_utils.basic import AnsibleModule
from ansible_collections.bodsch.core.plugins.module_utils.cache.cache_valid import cache_valid
from ansible_collections.bodsch.core.plugins.module_utils.directory import create_directory

__metaclass__ = type

DOCUMENTATION = r"""
---
module: github_releases
author: Bodo 'bodsch' Schulz <bodo@boone-schulz.de>
version_added: 0.9.9

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

        self.github_url = f"https://api.github.com/repos/{self.project}/{self.repository}/releases"

        self.cache_directory = f"{Path.home()}/.ansible/cache/github/{self.project}"
        self.cache_file_name = os.path.join(self.cache_directory, f"{self.repository}_releases.json")

        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

    def run(self):
        """
        """
        create_directory(self.cache_directory)
        status_code, data = self.latest_information()

        self.module.log(msg=f" - status_code: {status_code}")

        if status_code != 200:
            return dict(
                status=status_code,
                msg=f"No release information could be found under {self.github_url}.",
                # msg = data
            )

        download_url = ""
        urls = []

        if isinstance(data, list):
            """
            """
            for d in data:
                assets = d.get("assets", [])
                if assets and len(assets) > 0:
                    for url in assets:
                        urls.append(url.get("browser_download_url"))

        if len(urls) > 0:
            download_url = [x for x in urls if re.search(fr".*{self.version}.*{self.system}.*{self.architecture}.*", x)][0]

        # self.module.log(msg=f"= download_url: {download_url}")

        return dict(
            status=status_code,
            urls=urls,
            download_url=download_url
        )

    def latest_information(self):
        """
        """
        output = None

        out_of_cache = cache_valid(self.module, self.cache_file_name, self.cache_minutes, True)

        if not out_of_cache:
            self.module.log(msg=f" - read from cache  {self.cache_file_name}")
            with open(self.cache_file_name, "r") as f:
                output = json.loads(f.read())

                return 200, output

        if not output:
            self.module.log(msg=f" - read from url  {self.github_url}")
            status_code, output = self.__call_url()

            if status_code == 200:
                self.save_latest_information(output)

            return status_code, output

    def save_latest_information(self, data):
        """
        """
        with open(self.cache_file_name, "w") as f:
            json.dump(data, f, indent=2, sort_keys=True)

    def __call_url(self, method='GET', data=None):
        """
        """
        response = None

        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json;charset=utf-8"
        }

        try:
            authentication = (self.github_username, self.github_password)

            if method == "GET":
                response = requests.get(
                    self.github_url,
                    headers=headers,
                    auth=authentication
                )

            else:
                self.module.log(msg=f"{method} unsupported")
                pass

            response.raise_for_status()

            return response.status_code, response.json()

        except requests.exceptions.HTTPError as e:
            self.module.log(msg=f"HTTPError: {e}")

            status_code = e.response.status_code
            status_message = e.response.json()

            return status_code, status_message

        except ConnectionError as e:
            error_text = f"{type(e).__name__} {(str(e) if len(e.args) == 0 else str(e.args[0]))}"
            self.module.log(msg=f"ConnectionError: {error_text}")
            return 500, error_text

        except Exception as e:
            self.module.log(msg=f"ERROR   : {e}")

            return response.status_code, response.json()


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
