"""
forgejo_backend.py
==================

:class:`ReleaseBackend` implementation for Forgejo (and Gitea, which shares the
same ``/api/v1`` REST surface), built on :class:`BaseHTTPBackend`.

Forgejo's release API matches the GitHub/Gitea family (``tag_name`` / ``name`` /
``published_at`` / ``assets[].browser_download_url``) and uses the same
``Authorization: token`` auth scheme, so this backend only supplies the
endpoint URLs and reuses the shared default normalisers from
:class:`BaseHTTPBackend`.

Differences handled here
-------------------------
* A configurable ``api_url`` is required (self-hosted instances).
* ``draft`` releases are dropped by the shared normaliser.
* Auto-generated source archives are not returned by the assets endpoint
  (unlike GitLab's ``assets.sources``), so no extra filtering is needed beyond
  the resolver's existing metadata filter.

:author:  Bodo Schulz <bodo@boone-schulz.de>
:license: Apache-2.0
"""

from __future__ import annotations

from typing import Any

from ansible_collections.bodsch.scm.plugins.module_utils.release_backend import (BaseHTTPBackend,
                                                                                 JsonResult)

__metaclass__ = type


class ForgejoBackend(BaseHTTPBackend):
    """
    Release backend for Forgejo / Gitea instances.

    Inherits the resilient transport, on-disk cache, ``Authorization: token``
    auth scheme and the shared GitHub/Gitea-family normalisers from
    :class:`BaseHTTPBackend`.

    Attributes
    ----------
    See :class:`BaseHTTPBackend`.
    """

    def __init__(
        self,
        module: Any,
        owner: str,
        repository: str,
        api_url: str,
        token: str = None,
        cache_minutes: int = 60,
    ) -> None:
        """
        Initialise the Forgejo backend.

        :param module:        Ansible module instance (used for logging).
        :param owner:         Repository owner / organisation.
        :param repository:    Repository name.
        :param api_url:       Root of the Forgejo API, e.g.
                              ``"https://git.example.org/api/v1"``.
        :param token:         Optional Forgejo access token.
        :param cache_minutes: TTL for cached responses in minutes.
        """
        super().__init__(
            module=module,
            owner=owner,
            repository=repository,
            api_url=api_url,
            token=token,
            cache_minutes=cache_minutes,
            provider="forgejo",
        )

    def get_releases(self) -> JsonResult:
        """
        Fetch and normalise all releases.

        Calls ``GET {api_url}/repos/{owner}/{repo}/releases`` (paginated) and
        maps each non-draft release to ``{name, tag_name, published_at, url}``.

        :returns: ``(status_code, releases, error)``.
        """
        url = f"{self.api_url}/repos/{self.owner}/{self.repository}/releases"
        return self._cached_json(
            cache_filename="releases.json",
            url=url,
            params={"limit": 50, "page": 1},
            paginate=True,
            normalise=self._normalise_releases_default,
        )

    def get_assets(self, tag: str) -> JsonResult:
        """
        Fetch and normalise the assets of the release identified by *tag*.

        Calls ``GET {api_url}/repos/{owner}/{repo}/releases/tags/{tag}`` and
        maps each asset to ``{name, url, size}``.

        :param tag: Exact release tag (e.g. ``"v1.2.3"``).
        :returns:   ``(status_code, assets, error)``.
        """
        url = (
            f"{self.api_url}/repos/{self.owner}/{self.repository}"
            f"/releases/tags/{tag}"
        )
        return self._cached_json(
            cache_filename=f"assets_{tag}.json",
            url=url,
            params=None,
            paginate=False,
            normalise=self._normalise_assets_default,
        )
