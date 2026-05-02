#!/usr/bin/python3
# -*- coding: utf-8 -*-

# (c) 2022-2023, Bodo Schulz <bodo@boone-schulz.de>
# Apache-2.0 (see LICENSE or https://opensource.org/license/apache-2-0)
# SPDX-License-Identifier: Apache-2.0

from __future__ import absolute_import, print_function

import re
from enum import Enum
from pathlib import Path

from ansible.module_utils.basic import AnsibleModule
from ansible_collections.bodsch.scm.plugins.module_utils.github import GitHub
from ansible_collections.bodsch.scm.plugins.module_utils.release_finder import (
    ReleaseFinder,
)
from packaging.version import InvalidVersion, Version

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

        self.cache_directory = (
            f"{Path.home()}/.cache/ansible/github/{self.project}/{self.repository}"
        )

    def run(self):
        """ """
        gh_authentication = dict(token=self.github_password)

        gh = GitHub(
            self.module,
            owner=self.project,
            repository=self.repository,
            auth=gh_authentication,
        )
        gh.architecture(system=self.system, architecture=self.architecture)
        gh.enable_cache(cache_minutes=self.cache_minutes)

        status_code, gh_result, error = gh.get_all_releases(repo_url=self.github_url)

        if status_code == 419:
            return dict(
                failed=True,
                status=419,
                msg=(
                    "An internal error has occurred. Probably a GitHub request could "
                    "not be parsed properly. Please contact the developer."
                ),
                stderr=error,
            )

        if status_code != 200:
            return dict(
                failed=True,
                status=status_code,
                msg="An error has occurred with a request against GitHub.",
                stderr=error,
            )

        if not gh_result or not isinstance(gh_result, list):
            return dict(
                status=500,
                msg=f"No release information could be found under {self.github_url}.",
            )

        # self.module.log(msg=f"  - gh_result entries: {len(gh_result)}")

        # Suche nach dem Release, dessen Version (aus name oder tag_name) zur
        # gewünschten Version passt – robust gegenüber beschreibenden Namen.
        matching_releases = [
            x for x in gh_result if self._release_matches_version(x, self.version)
        ]

        # self.module.log(msg=f"  - matching_releases: {matching_releases}")

        if not matching_releases:
            return dict(
                status=500,
                msg=(
                    f"No release matching version '{self.version}' found "
                    f"under {self.github_url}."
                ),
            )

        download_urls = matching_releases[0].get("download_urls", [])

        # self.module.log(msg=f"  - download_urls: {download_urls}")

        try:
            if not download_urls:
                return dict(status=500, msg="Release found but has no download URLs.")

            matches = [
                x
                for x in download_urls
                if re.search(
                    rf".*{re.escape(self.version.lstrip('v'))}.*"
                    rf"{re.escape(self.system)}.*{re.escape(self.architecture)}.*",
                    x,
                )
            ]

            if matches:
                return dict(
                    status=200,
                    urls=download_urls,
                    download_url=matches[0],
                )
            else:
                return dict(status=500, msg="No matching download URL found.")

        except Exception as e:
            self.module.log(msg=f"Error: {e}")
            return dict(status=500, msg=str(e))

    # ------------------------------------------------------------------------------------------
    # private helpers

    def _release_matches_version(self, release: dict, target_version: str) -> bool:
        """
        Prüft robust, ob ein Release-Eintrag zur gesuchten Version gehört.

        Vergleichsreihenfolge pro Feld (name, tag_name):
          1. Exakter String-Vergleich nach 'v'-Strip
          2. SemVer-Vergleich nach Versionsextraktion aus beschreibendem Namen

        Beispiele, die alle zu version="2.3.0" passen:
          name="2.3.0",      tag_name="v2.3.0"
          name="GLAuth v2.3.0", tag_name="v2.3.0"
          name="v2.3.0",     tag_name="project-2.3.0"
        """
        target_plain = target_version.lstrip("v")

        # SemVer-Objekt für präzisen Vergleich (einmalig, optional)
        try:
            target_ver = Version(target_plain)
        except InvalidVersion:
            target_ver = None

        for field in ("name", "tag_name"):
            raw = release.get(field) or ""

            # 1. Exakter Vergleich
            if raw.lstrip("v") == target_plain:
                return True

            # 2. Versionsextraktion + SemVer-Vergleich
            extracted = ReleaseFinder.extract_version_from_string(raw)
            if extracted:
                if extracted == target_plain:
                    return True
                if target_ver is not None:
                    try:
                        if Version(extracted) == target_ver:
                            return True
                    except InvalidVersion:
                        pass

        return False


def main():
    """ """
    args = dict(
        project=dict(required=True, type=str),
        repository=dict(required=True, type=str),
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
        user=dict(required=False, type=str),
        password=dict(required=False, type=str, no_log=True),
        cache=dict(required=False, default=120),
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
if __name__ == "__main__":
    main()
