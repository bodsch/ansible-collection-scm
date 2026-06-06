#!/usr/bin/python3
# -*- coding: utf-8 -*-

# (c) 2022-2025, Bodo Schulz <bodo@boone-schulz.de>
# Apache-2.0 (see LICENSE or https://opensource.org/license/apache-2-0)
# SPDX-License-Identifier: Apache-2.0

from __future__ import absolute_import, print_function

from ansible.module_utils.basic import AnsibleModule
from ansible_collections.bodsch.scm.plugins.module_utils.github_backend import (
    GitHubBackend,
)
from ansible_collections.bodsch.scm.plugins.module_utils.forgejo_backend import (
    ForgejoBackend,
)
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
module: scm_release
author: Bodo 'bodsch' Schulz <bodo@boone-schulz.de>
version_added: 1.1.0

short_description: Resolve a release to a downloadable, verifiable artefact across SCM providers.
description:
  - Provider-independent successor to M(bodsch.scm.github_release).
  - Performs a single cached lookup over a repository's releases and returns
    everything required to download and verify a release artefact in one step,
    namely the resolved version, the artefact download URL, the artefact
    filename and the matching checksum.
  - Selects the backend via O(provider). C(github) targets github.com;
    C(forgejo) targets a Forgejo or Gitea instance (requires O(host)).
  - All matching and checksum logic is shared with M(bodsch.scm.github_release)
    through the common resolver; only the API transport differs per provider.

options:
  provider:
    description:
      - The SCM provider to query.
    type: str
    required: false
    default: github
    choices: [github, forgejo]
  host:
    description:
      - Base URL of a self-hosted instance, for example
        V(https://git.example.org).
      - Required for O(provider=forgejo). Ignored for O(provider=github).
    type: str
    required: false
  project:
    description:
      - Project, owner or namespace that contains the repository.
    type: str
    required: true
  repository:
    description:
      - Repository name within the project.
    type: str
    required: true
  version:
    description:
      - Requested version. Use V(latest) or a concrete version with or without
        a leading C(v).
    type: str
    required: true
  architecture:
    description:
      - Target CPU architecture used to select the artefact. Synonyms are
        handled automatically (for example C(x86_64)/C(amd64)).
    type: str
    required: false
    default: x86_64
  system:
    description:
      - Target operating system used to select the artefact.
    type: str
    required: false
    default: Linux
  asset:
    description:
      - Explicit artefact filename template overriding the heuristic.
      - "Placeholders: C({version}), C({tag}), C({system}) (lowercased),
        C({arch}) (raw architecture)."
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
      - Ordered archive extension preference used to disambiguate.
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
      - Keywords excluded when resolving O(version=latest).
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
      - Optional username (informational; authentication uses O(password)).
    type: str
    required: false
  password:
    description:
      - Optional access token for the provider.
    type: str
    required: false
  cache:
    description:
      - Validity of cached release metadata in seconds.
    type: int
    required: false
    default: 60

seealso:
  - module: bodsch.scm.github_release
"""

EXAMPLES = r"""
- name: resolve a release from a self-hosted Forgejo instance
  bodsch.scm.scm_release:
    provider: forgejo
    host: "https://git.boone-schulz.de"
    project: bodsch
    repository: nextcloud-ical-backup
    version: latest
    architecture: "{{ ansible_facts.architecture }}"
    system: "{{ ansible_facts.system }}"
    password: "{{ lookup('env', 'FORGEJO_TOKEN') | default(omit) }}"
  register: _release

- name: download and verify
  ansible.builtin.get_url:
    url: "{{ _release.download_url }}"
    dest: "/tmp/{{ _release.file }}"
    checksum: "{{ _release.checksum_string | default(omit) }}"
    mode: "0640"

- name: same module, GitHub provider
  bodsch.scm.scm_release:
    provider: github
    project: prometheus
    repository: prometheus
    version: "2.53.0"
    password: "{{ lookup('env', 'GH_TOKEN') | default(omit) }}"
  register: _gh_release
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
tag:
  description: Git tag of the resolved release.
  type: str
  returned: success
file:
  description: Filename of the selected artefact asset.
  type: str
  returned: success
download_url:
  description: Direct download URL of the selected artefact asset.
  type: str
  returned: success
checksum:
  description: Lowercase hex checksum, or V(None) when no checksum source exists.
  type: str
  returned: success
checksum_algorithm:
  description: Checksum algorithm name, or V(None).
  type: str
  returned: success
checksum_string:
  description: Convenience value C(<algorithm>:<hash>) for M(ansible.builtin.get_url).
  type: str
  returned: success
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
  description: Asset names considered when artefact selection failed.
  type: list
  elements: str
  returned: on ambiguous or empty match
msg:
  description: Error message on failure.
  type: str
  returned: on failure
"""


class ScmRelease:
    """
    Generic, provider-dispatching release resolver module wrapper.

    Builds the appropriate :class:`ReleaseBackend` for the requested provider
    and delegates resolution to :class:`ReleaseResolver`.

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
        self.provider = module.params.get("provider")
        self.host = module.params.get("host")
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

    def _build_backend(self):
        """
        Construct the backend for the configured provider.

        :returns:            A :class:`ReleaseBackend` implementation.
        :raises ValueError:  When required provider options are missing.
        """
        if self.provider == "github":
            return GitHubBackend(
                module=self.module,
                owner=self.project,
                repository=self.repository,
                token=self.github_password,
                cache_minutes=self.cache_minutes,
            )

        if self.provider == "forgejo":
            if not self.host:
                raise ValueError("provider 'forgejo' requires the 'host' option.")
            return ForgejoBackend(
                module=self.module,
                owner=self.project,
                repository=self.repository,
                api_url=f"{self.host.rstrip('/')}/api/v1",
                token=self.github_password,
                cache_minutes=self.cache_minutes,
            )

        raise ValueError(f"Unsupported provider: {self.provider!r}")

    def run(self) -> dict:
        """
        Execute the resolution and build the module result.

        :returns: Result dict for ``exit_json`` / ``fail_json``.
        """
        try:
            backend = self._build_backend()
        except ValueError as error:
            return dict(failed=True, changed=False, status=400, msg=str(error))

        resolver = ReleaseResolver(
            module=self.module,
            backend=backend,
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
                failed=True, changed=False, status=error.status, msg=error.msg
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
        provider=dict(
            required=False,
            type="str",
            default="github",
            choices=["github", "forgejo"],
        ),
        host=dict(required=False, type="str"),
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
        required_if=[["provider", "forgejo", ["host"]]],
    )

    api = ScmRelease(module)
    result = api.run()

    module.log(msg=f"= result : {result}")

    if result.get("failed"):
        module.fail_json(**result)

    module.exit_json(**result)


# import module snippets
if __name__ == "__main__":
    main()
