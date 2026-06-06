#!/usr/bin/python3
# -*- coding: utf-8 -*-

# (c) 2022-2025, Bodo Schulz <bodo@boone-schulz.de>
# Apache-2.0 (see LICENSE or https://opensource.org/license/apache-2-0)
# SPDX-License-Identifier: Apache-2.0

from __future__ import absolute_import, print_function

from pathlib import Path

from ansible.module_utils.basic import AnsibleModule
from ansible_collections.bodsch.scm.plugins.module_utils.github import GitHub
from ansible_collections.bodsch.scm.plugins.module_utils.release_resolver import (
    ReleaseResolver,
    ResolverError,
)

__metaclass__ = type

ANSIBLE_METADATA = {
    "metadata_version": "0.1",
    "status": ["preview"],
    "supported_by": "community",
}

DOCUMENTATION = r"""
---
module: github_release
author: Bodo 'bodsch' Schulz <bodo@boone-schulz.de>
version_added: 1.0.0

short_description: Resolve a GitHub release to a downloadable, verifiable artefact.
description:
  - Performs a single cached lookup over a repository's releases and returns
    everything required to download and verify a release artefact in one step,
    namely the resolved version, the artefact download URL, the artefact
    filename and the matching checksum (hash, algorithm and source).
  - Replaces the previous three-step workflow
    (M(bodsch.scm.github_latest) plus M(bodsch.scm.github_checksum) plus manual
    URL assembly) that maintained three independent matching heuristics and
    threaded the version through C(set_fact).
  - Artefact selection uses a hybrid strategy. By default a synonym-aware
    heuristic matches the operating system and CPU architecture against the
    asset names (for example C(x86_64) also matches C(amd64), C(aarch64) also
    matches C(arm64)) followed by an archive extension preference. The
    O(asset) template or O(asset_regex) options pin the match deterministically
    for projects with unusual naming.
  - Checksum resolution handles aggregate checksum files (GNU coreutils and BSD
    formats), per-artefact sidecar files and the absence of any checksum, in
    which case RV(checksum) is V(None) and the module does B(not) fail.

options:
  project:
    description:
      - Defines the project (owner or organisation) in which the repository
        was created.
      - "For example: B(prometheus)/alertmanager"
    type: str
    required: true
  repository:
    description:
      - Defines the repository maintained underneath the given project.
      - "For example: prometheus/B(alertmanager)"
    type: str
    required: true
  version:
    description:
      - Requested version. Use V(latest) to resolve the highest non-excluded
        SemVer release, or a concrete version with or without a leading C(v)
        (for example V(2.53.0) or V(v2.53.0)).
    type: str
    required: true
  architecture:
    description:
      - Target CPU architecture used to select the artefact, typically taken
        from C(ansible_facts.architecture).
      - Synonyms are handled automatically (for example C(x86_64)/C(amd64),
        C(aarch64)/C(arm64)).
    type: str
    required: false
    default: x86_64
  system:
    description:
      - Target operating system used to select the artefact, typically taken
        from C(ansible_facts.system).
    type: str
    required: false
    default: Linux
  asset:
    description:
      - Explicit artefact filename template overriding the heuristic.
      - "Supported placeholders: C({version}) (without leading C(v)),
        C({tag}) (raw tag), C({system}) (lowercased) and C({arch}) (raw
        architecture)."
      - Mutually exclusive with O(asset_regex).
    type: str
    required: false
  asset_regex:
    description:
      - Regular expression matched against asset names, overriding the
        heuristic.
      - Mutually exclusive with O(asset).
    type: str
    required: false
  extensions:
    description:
      - Ordered archive extension preference used to disambiguate multiple
        matching artefacts. The first extension with a match wins.
    type: list
    elements: str
    required: false
    default:
      - .tar.gz
      - .tgz
      - .tar.xz
      - .tar.bz2
      - .zip
  exclude_keywords:
    description:
      - Keywords excluded when resolving O(version=latest). A release whose
        name or tag contains any keyword (case-insensitive) is skipped.
    type: list
    elements: str
    required: false
    default:
      - beta
      - rc
      - preview
      - alpha
      - nightly
  user:
    description:
      - Optional GitHub username (currently informational; authentication uses
        the token supplied via O(password)).
    type: str
    required: false
  password:
    description:
      - Optional GitHub personal access token. Raises the API rate limit and
        enables access to private repositories.
    type: str
    required: false
  cache:
    description:
      - Validity of cached release metadata in seconds. Prevents unnecessary
        repeated GitHub API calls.
    type: int
    required: false
    default: 60
"""

EXAMPLES = r"""
- name: resolve prometheus release (latest)
  delegate_to: localhost
  become: false
  run_once: true
  bodsch.scm.github_release:
    project: prometheus
    repository: prometheus
    version: latest
    architecture: "{{ ansible_facts.architecture }}"
    system: "{{ ansible_facts.system }}"
    user: "{{ lookup('env', 'GH_USER') | default(omit) }}"
    password: "{{ lookup('env', 'GH_TOKEN') | default(omit) }}"
  register: _release

- name: download and verify in a single get_url
  delegate_to: localhost
  become: false
  run_once: true
  ansible.builtin.get_url:
    url: "{{ _release.download_url }}"
    dest: "/tmp/{{ _release.file }}"
    checksum: "{{ _release.checksum_string | default(omit) }}"
    mode: "0640"

- name: pin an unusual asset name explicitly
  bodsch.scm.github_release:
    project: someorg
    repository: sometool
    version: "1.4.2"
    asset: "sometool-{version}-{system}-{arch}-musl.tar.gz"
"""

RETURN = r"""
failed:
  description: Whether the resolution failed.
  type: bool
  returned: always
changed:
  description: Always V(false); this module performs no changes.
  type: bool
  returned: always
status:
  description: HTTP-like status code of the operation.
  type: int
  returned: always
version:
  description: Resolved version without a leading C(v).
  type: str
  returned: success
  sample: "2.53.0"
tag:
  description: Git tag of the resolved release.
  type: str
  returned: success
  sample: "v2.53.0"
file:
  description: Filename of the selected artefact asset.
  type: str
  returned: success
  sample: "prometheus-2.53.0.linux-amd64.tar.gz"
download_url:
  description: Direct download URL of the selected artefact asset.
  type: str
  returned: success
checksum:
  description: Lowercase hex checksum of the artefact, or V(None) when no
    checksum source exists.
  type: str
  returned: success
checksum_algorithm:
  description: Checksum algorithm name (for example V(sha256)), or V(None).
  type: str
  returned: success
checksum_string:
  description: Convenience value C(<algorithm>:<hash>) for direct use in
    M(ansible.builtin.get_url), or V(None).
  type: str
  returned: success
  sample: "sha256:e3b0c44298fc1c149afbf4c8996fb924..."
checksum_url:
  description: Download URL of the checksum source asset, or V(None).
  type: str
  returned: success
checksum_source:
  description: Origin of the checksum.
  type: str
  returned: success
  choices: [per_artifact, aggregate, none]
assets:
  description: Names of all assets attached to the resolved release.
  type: list
  elements: str
  returned: success
candidates:
  description: Asset names considered when artefact selection failed or was
    ambiguous.
  type: list
  elements: str
  returned: on ambiguous or empty match
msg:
  description: Error message on failure.
  type: str
  returned: on failure
"""


class GithubRelease:
    """
    Ansible module wrapper around :class:`ReleaseResolver`.

    Builds a configured :class:`GitHub` client, delegates the resolution to
    :class:`ReleaseResolver` and maps the result (or a :class:`ResolverError`)
    onto the module's return dictionary.

    Attributes
    ----------
    module : AnsibleModule
        The calling Ansible module instance.
    """

    def __init__(self, module: AnsibleModule) -> None:
        """
        Initialise the wrapper from the module parameters.

        :param module: The Ansible module instance.
        """
        self.module = module

        self.project = module.params.get("project")
        self.repository = module.params.get("repository")
        self.version = module.params.get("version")
        self.architecture = module.params.get("architecture")
        self.system = module.params.get("system")
        self.asset = module.params.get("asset")
        self.asset_regex = module.params.get("asset_regex")
        self.extensions = module.params.get("extensions")
        self.exclude_keywords = module.params.get("exclude_keywords")
        self.github_username = module.params.get("user")
        self.github_password = module.params.get("password")
        self.cache_minutes = int(module.params.get("cache"))

        # Retained for parity with the other modules; the cache directory itself
        # is created by GitHubCache via GitHub.enable_cache().
        self.cache_directory = (
            f"{Path.home()}/.cache/ansible/github/{self.project}/{self.repository}"
        )

    def run(self) -> dict:
        """
        Execute the resolution and build the module result.

        :returns: Result dict for ``exit_json`` / ``fail_json``.
        """
        gh = GitHub(
            self.module,
            owner=self.project,
            repository=self.repository,
            auth=dict(token=self.github_password),
        )
        gh.enable_cache(cache_minutes=self.cache_minutes)

        resolver = ReleaseResolver(
            module=self.module,
            github=gh,
            system=self.system,
            architecture=self.architecture,
            asset=self.asset,
            asset_regex=self.asset_regex,
            extensions=self.extensions,
            exclude_keywords=self.exclude_keywords,
        )

        try:
            resolved = resolver.resolve(self.version)
        except ResolverError as error:
            result = dict(
                failed=True,
                changed=False,
                status=error.status,
                msg=error.msg,
            )
            if error.candidates:
                result["candidates"] = error.candidates
            return result

        result = dict(failed=False, changed=False, status=200)
        result.update(resolved.to_dict())
        return result


def main() -> None:
    """
    Module entry point: define the argument spec, run, and exit.
    """
    args = dict(
        project=dict(required=True, type="str"),
        repository=dict(required=True, type="str"),
        version=dict(required=True, type="str"),
        architecture=dict(required=False, type="str", default="x86_64"),
        system=dict(required=False, type="str", default="Linux"),
        asset=dict(required=False, type="str"),
        asset_regex=dict(required=False, type="str"),
        extensions=dict(
            required=False,
            type="list",
            elements="str",
            default=[".tar.gz", ".tgz", ".tar.xz", ".tar.bz2", ".zip"],
        ),
        exclude_keywords=dict(
            required=False,
            type="list",
            elements="str",
            default=["beta", "rc", "preview", "alpha", "nightly"],
        ),
        user=dict(required=False, type="str"),
        password=dict(required=False, type="str", no_log=True),
        cache=dict(required=False, type="int", default=60),
    )

    module = AnsibleModule(
        argument_spec=args,
        supports_check_mode=True,
        mutually_exclusive=[["asset", "asset_regex"]],
    )

    api = GithubRelease(module)
    result = api.run()

    module.log(msg=f"= result : {result}")

    if result.get("failed"):
        module.fail_json(**result)

    module.exit_json(**result)


# import module snippets
if __name__ == "__main__":
    main()
