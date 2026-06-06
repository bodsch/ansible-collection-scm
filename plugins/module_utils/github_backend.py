"""
github_backend.py
=================

:class:`ReleaseBackend` implementation for github.com (and GitHub Enterprise via
a custom ``api_url``), built natively on :class:`BaseHTTPBackend`.

This replaces the earlier thin adapter that wrapped the legacy ``GitHub`` class.
GitHub, Gitea and Forgejo share the same release/asset JSON field names and the
same ``Authorization: token`` auth scheme, so this backend only supplies the
endpoint URLs and the GitHub ``Accept`` header; release/asset normalisation is
the shared default from :class:`BaseHTTPBackend`.

.. note::
    The legacy ``GitHub`` module_util (``github.py``) is unchanged and still
    backs the ``github_latest`` / ``github_releases`` / ``github_checksum``
    modules. The ``github_release`` module and the resolver's ``github=``
    compatibility path now route through this native backend instead.

:author:  Bodo Schulz <bodo@boone-schulz.de>
:license: Apache-2.0
"""

from __future__ import annotations

from typing import Any

from ansible_collections.bodsch.scm.plugins.module_utils.release_backend import (BaseHTTPBackend,
                                                                                 JsonResult)

__metaclass__ = type


class GitHubBackend(BaseHTTPBackend):
    """
    Release backend for GitHub.

    Inherits the resilient transport, on-disk cache and
    ``Authorization: token`` auth scheme from :class:`BaseHTTPBackend`, and the
    shared GitHub/Gitea-family normalisers.

    Attributes
    ----------
    See :class:`BaseHTTPBackend`.
    """

    def __init__(
        self,
        module: Any,
        owner: str,
        repository: str,
        token: str = None,
        cache_minutes: int = 60,
        api_url: str = "https://api.github.com",
    ) -> None:
        """
        Initialise the GitHub backend.

        :param module:        Ansible module instance (used for logging).
        :param owner:         Repository owner / organisation.
        :param repository:    Repository name.
        :param token:         Optional GitHub personal access token. Raises the
                              API rate limit and grants access to private repos.
        :param cache_minutes: TTL for cached responses in minutes.
        :param api_url:       API root. Defaults to ``https://api.github.com``;
                              override for GitHub Enterprise
                              (``https://<host>/api/v3``).
        """
        super().__init__(
            module=module,
            owner=owner,
            repository=repository,
            api_url=api_url,
            token=token,
            cache_minutes=cache_minutes,
            provider="github",
        )
        # GitHub prefers its versioned vendor media type.
        self.headers["Accept"] = "application/vnd.github.v3+json"

    def get_releases(self) -> JsonResult:
        """
        Fetch and normalise all releases.

        Calls ``GET {api_url}/repos/{owner}/{repo}/releases`` (paginated,
        100 per page) and maps each non-draft release to
        ``{name, tag_name, published_at, url}``.

        :returns: ``(status_code, releases, error)``.
        """
        url = f"{self.api_url}/repos/{self.owner}/{self.repository}/releases"
        return self._cached_json(
            cache_filename="releases.json",
            url=url,
            params={"per_page": 100},
            paginate=True,
            normalise=self._normalise_releases_default,
        )

    def get_assets(self, tag: str) -> JsonResult:
        """
        Fetch and normalise the assets of the release identified by *tag*.

        Calls ``GET {api_url}/repos/{owner}/{repo}/releases/tags/{tag}`` and
        maps each asset to ``{name, url, size}``.

        :param tag: Exact release tag (e.g. ``"v2.53.0"``).
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
