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
        self.module = module

        # self.module.log("ForgejoBackend:__init__()")

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
        # self.module.log("ForgejoBackend:get_releases()")

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
        # self.module.log(f"ForgejoBackend:get_assets(tag: {tag})")

        url = (
            f"{self.api_url}/repos/{self.owner}/{self.repository}"
            f"/releases/tags/{tag}"
        )

        self.module.log(f"  - url: {url}")

        status, assets, error = self._cached_json(
            cache_filename=f"assets_{tag}.json",
            url=url,
            params=None,
            paginate=False,
            normalise=self._normalise_assets_default,
        )

        if status == 200 and not assets:
            # Some pipelines publish their artefacts to the generic package
            # registry instead of attaching them to the release.
            return self._get_package_assets(tag)

        return (status, assets, error)

    def _get_package_assets(self, tag: str) -> JsonResult:
        """
        Fetch the files of the generic package ``{repository}`` in version
        *tag* from the Forgejo package registry.

        Calls ``GET {api_url}/packages/{owner}/generic/{repo}/{version}/files``
        and maps each file to ``{name, url, size}``, where *url* is the
        registry download endpoint
        ``{host}/api/packages/{owner}/generic/{repo}/{version}/{file}``.

        Tries the raw tag first, then the tag without a leading ``"v"``.

        :param tag: Release tag used as package version (e.g. ``"1.2.0"``).
        :returns:   ``(status_code, assets, error)``; an empty list when no
                    matching package exists.
        """
        # self.module.log(f"ForgejoBackend:_get_package_assets(tag: {tag})")

        # ".../api/v1" -> ".../api/packages"
        packages_url = f"{self.api_url.rsplit('/v1', 1)[0]}/packages"

        for version in dict.fromkeys([tag, tag.lstrip("v")]):
            url = (
                f"{self.api_url}/packages/{self.owner}/generic"
                f"/{self.repository}/{version}/files"
            )
            download_base = (
                f"{packages_url}/{self.owner}/generic/{self.repository}/{version}"
            )

            status, assets, error = self._cached_json(
                cache_filename=f"package_assets_{version}.json",
                url=url,
                params=None,
                paginate=False,
                normalise=lambda raw, base=download_base: [
                    {
                        "name": f.get("name"),
                        "url": f"{base}/{f.get('name')}",
                        "size": f.get("Size", f.get("size")),
                    }
                    for f in raw
                    if f.get("name")
                ],
            )
            if status == 200 and assets:
                return (status, assets, error)

        return (200, [], None)
