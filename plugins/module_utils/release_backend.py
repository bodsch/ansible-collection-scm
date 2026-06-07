"""
release_backend.py
==================

Backend abstraction for release providers (GitHub, Forgejo/Gitea, and — later —
GitLab).

A *backend* is the thin seam between :class:`ReleaseResolver` (all the
provider-independent matching/checksum logic) and a concrete forge's REST API.
The resolver only ever touches the small surface declared by
:class:`ReleaseBackend`; everything else (synonym matching, checksum parsing,
version normalisation) is shared and written once.

This module provides:

* :class:`ReleaseBackend` — the structural contract (``typing.Protocol``) every
  backend must satisfy.
* :class:`BaseHTTPBackend` — a concrete base supplying the resilient HTTP
  transport (retries, ``Link``-header pagination, optional rate-limit
  detection) plus on-disk caching, so a new backend only implements endpoint
  URLs and response normalisation.

Normalised data shapes
-----------------------
``get_releases`` returns::

    {"name": str, "tag_name": str, "published_at": str, "url": str}

``get_assets`` returns::

    {"name": str, "url": str, "size": Optional[int]}

``get_text`` returns the raw text body of a download URL (e.g. a checksum file).

:author:  Bodo Schulz <bodo@boone-schulz.de>
:license: Apache-2.0
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Protocol, Tuple
from urllib.parse import urlparse

import requests
from ansible_collections.bodsch.scm.plugins.module_utils.github_cache import GitHubCache
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

__metaclass__ = type

# Result tuple shared by all backend methods: (status_code, payload, error).
JsonResult = Tuple[int, List[Dict[str, Any]], Optional[str]]
TextResult = Tuple[int, Optional[str], Optional[str]]


class ReleaseBackend(Protocol):
    """
    Structural contract implemented by every release provider backend.

    The resolver depends only on this surface, which keeps provider-specific
    quirks out of the shared matching logic.

    Attributes
    ----------
    owner : str
        Repository owner / organisation / namespace.
    repository : str
        Repository / project name.
    """

    owner: str
    repository: str

    def get_releases(self) -> JsonResult:
        """
        Return all releases normalised to
        ``{name, tag_name, published_at, url}``.

        :returns: ``(status_code, releases, error)``.
        """
        ...

    def get_assets(self, tag: str) -> JsonResult:
        """
        Return the assets of the release identified by *tag*, normalised to
        ``{name, url, size}``.

        :param tag: Exact release tag.
        :returns:   ``(status_code, assets, error)``.
        """
        ...

    def get_text(self, url: str) -> TextResult:
        """
        Fetch the raw text body of *url* (e.g. a checksum file).

        :param url: Direct download URL of a text resource.
        :returns:   ``(status_code, text, error)``.
        """
        ...


class BaseHTTPBackend:
    """
    Concrete base providing HTTP transport and caching for REST backends.

    Subclasses implement :meth:`get_releases` and :meth:`get_assets` (endpoint
    URLs + response normalisation) and may override :meth:`_auth_header` to
    change the authentication scheme.  :meth:`get_text`, the request transport
    and the cache are provided here.

    Caching mirrors the layout used by the existing GitHub client but is
    namespaced per provider **and** host to avoid collisions between, e.g.,
    ``github.com`` and a self-hosted Forgejo instance::

        ~/.cache/ansible/<provider>/<host>/<owner>/<repository>/

    Attributes
    ----------
    module : AnsibleModule
        Ansible module instance used for logging.
    owner : str
        Repository owner / namespace.
    repository : str
        Repository / project name.
    api_url : str
        Root URL of the provider's REST API (without trailing slash).
    headers : dict
        Default HTTP headers sent with every request.
    cache : GitHubCache
        On-disk cache helper.
    """

    def __init__(
        self,
        module: Any,
        owner: str,
        repository: str,
        api_url: str,
        token: Optional[str] = None,
        cache_minutes: int = 60,
        provider: str = "generic",
    ) -> None:
        """
        Initialise the backend transport and cache.

        :param module:        Ansible module instance (used for logging).
        :param owner:         Repository owner / namespace.
        :param repository:    Repository / project name.
        :param api_url:       Root URL of the provider's REST API
                              (e.g. ``"https://git.example.org/api/v1"``).
        :param token:         Optional access token.  Passed to
                              :meth:`_auth_header` to build the auth header.
        :param cache_minutes: TTL for cached responses in minutes.
        :param provider:      Short provider label used in the cache path
                              (e.g. ``"forgejo"``).
        """
        self.module = module
        self.owner = owner
        self.repository = repository
        self.api_url = api_url.rstrip("/")

        self.headers: Dict[str, str] = {"Accept": "application/json"}
        if token:
            self.headers.update(self._auth_header(token))

        host = urlparse(self.api_url).netloc or "unknown-host"
        cache_dir = (
            f"{Path.home()}/.cache/ansible/{provider}/{host}/{owner}/{repository}"
        )
        self.cache = GitHubCache(
            module=module,
            cache_dir=cache_dir,
            cache_file=None,
            cache_minutes=cache_minutes,
        )

    # ------------------------------------------------------------------------------------------
    # Overridable hooks

    def _auth_header(self, token: str) -> Dict[str, str]:
        """
        Build the authentication header for *token*.

        Default scheme is ``Authorization: token <token>`` (used by GitHub and
        Forgejo/Gitea).  Override for providers using a different scheme (e.g.
        GitLab's ``PRIVATE-TOKEN``).

        :param token: Access token.
        :returns:     Header dict merged into :attr:`headers`.
        """
        return {"Authorization": f"token {token}"}

    # ------------------------------------------------------------------------------------------
    # Contract methods to be implemented by subclasses

    def get_releases(self) -> JsonResult:
        """Return normalised releases; implemented by subclasses."""
        raise NotImplementedError

    def get_assets(self, tag: str) -> JsonResult:
        """Return normalised assets for *tag*; implemented by subclasses."""
        raise NotImplementedError

    # ------------------------------------------------------------------------------------------
    # Shared transport

    def get_text(self, url: str) -> TextResult:
        """
        Fetch the raw text body of *url*.

        Sends ``Accept: */*`` (overriding the JSON default) so file servers do
        not reject the request, while keeping any authentication header for
        private instances.

        :param url: Direct download URL of a text resource.
        :returns:   ``(status_code, text, error)``; *text* is ``None`` on error.
        """
        headers = dict(self.headers)
        headers["Accept"] = "*/*"

        status, body, error = self._request(
            url, headers=headers, expect_json=False, paginate=False
        )
        if status != 200:
            return (status, None, error)
        return (200, body, None)

    def _cached_json(
        self,
        cache_filename: str,
        url: str,
        params: Optional[dict],
        paginate: bool,
        normalise: Callable[[List[Dict[str, Any]]], List[Dict[str, Any]]],
    ) -> JsonResult:
        """
        Fetch JSON with on-disk caching and normalisation.

        On a cache hit the stored (already normalised) data is returned.  On a
        miss the live response is normalised, cached and returned.

        :param cache_filename: Cache file name within the cache directory.
        :param url:            Request URL.
        :param params:         Optional query parameters.
        :param paginate:       Whether to follow ``Link``-header pagination.
        :param normalise:      Callable mapping the raw list to the normalised
                               list.
        :returns:              ``(status_code, normalised, error)``.
        """
        cache_path = self.cache.cache_path(cache_filename)
        cached = self.cache.cached_data(cache_path)
        if cached is not None:
            return (200, cached, None)

        status, raw, error = self._request(
            url, headers=self.headers, params=params, expect_json=True,
            paginate=paginate,
        )
        if status != 200:
            return (status, [], error)

        normalised = normalise(raw)
        self.cache.write_cache(cache_path, normalised)
        return (200, normalised, None)

    def _request(
        self,
        url: str,
        headers: Dict[str, str],
        params: Optional[dict] = None,
        expect_json: bool = True,
        paginate: bool = True,
    ) -> Tuple[int, Any, Optional[str]]:
        """
        Execute a resilient HTTP GET.

        Features: 3 retries with exponential backoff on 429/5xx, optional
        ``Link``-header pagination (results accumulated into one list), and a
        best-effort GitHub-style rate-limit short-circuit when the provider
        exposes ``X-RateLimit-Remaining``.

        :param url:         Request URL.
        :param headers:     Request headers.
        :param params:      Optional query parameters (first page only).
        :param expect_json: ``True`` to decode JSON into a list; ``False`` to
                            return the response text.
        :param paginate:    ``True`` to follow ``Link`` pagination.
        :returns:           ``(status_code, data, error)`` where *data* is a
                            list (JSON) or str (text); status ``419`` indicates
                            a transport/parse error.
        """
        session = requests.Session()
        retry = Retry(
            total=3,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["GET"],
        )
        session.mount("https://", HTTPAdapter(max_retries=retry))
        session.mount("http://", HTTPAdapter(max_retries=retry))

        result: List[dict] = []

        while url:
            try:
                response = session.get(
                    url, headers=headers, params=params, timeout=15
                )
                self.module.log(msg=f"- response: {response.status_code} {url}")

                if (
                    response.status_code == 403
                    and response.headers.get("X-RateLimit-Remaining") == "0"
                ):
                    reset = int(response.headers.get("X-RateLimit-Reset", 0))
                    wait = max(reset - int(time.time()), 1)
                    error = f"Rate limit exceeded. Retry in {wait} seconds."
                    self.module.log(error)
                    return (429, [], error)

                response.raise_for_status()

                if not expect_json:
                    return (200, response.text, None)

                data = response.json()
                if not isinstance(data, list):
                    data = [data]
                result.extend(data)

                if not paginate:
                    break

                url = self._next_link(response.headers.get("Link", ""))
                params = None  # query params only on the first page

            except requests.exceptions.RequestException as exc:
                error = f"Request failed: {exc}"
                self.module.log(error)
                return (419, [], error)
            except ValueError as exc:
                error = f"Error parsing JSON: {exc}"
                self.module.log(error)
                return (419, [], error)

        return (200, result, None)

    @staticmethod
    def _next_link(link_header: str) -> Optional[str]:
        """
        Extract the ``rel="next"`` URL from an RFC 5988 ``Link`` header.

        :param link_header: Raw ``Link`` header value (may be empty).
        :returns:           The next-page URL, or ``None`` when absent.
        """
        for part in link_header.split(","):
            if 'rel="next"' in part:
                start = part.find("<") + 1
                end = part.find(">")
                if 0 < start < end:
                    return part[start:end]
        return None

    # ------------------------------------------------------------------------------------------
    # Default normalisers (GitHub / Gitea / Forgejo family)
    #
    # GitHub, Gitea and Forgejo share the same release and asset JSON field
    # names, so both GitHubBackend and ForgejoBackend reuse these. Providers
    # with a different shape (e.g. GitLab) supply their own normalisers.

    @staticmethod
    def _normalise_releases_default(
        raw: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Map raw GitHub/Gitea/Forgejo release objects to the normalised shape.

        Draft releases are dropped (they are never a published, downloadable
        release).

        :param raw: List of raw release dicts.
        :returns:   Normalised ``{name, tag_name, published_at, url}`` dicts.
        """
        out: List[Dict[str, Any]] = []
        for release in raw:
            if release.get("draft"):
                continue
            out.append(
                {
                    "name": release.get("name", "N/A"),
                    "tag_name": release.get("tag_name", "N/A"),
                    "published_at": release.get("published_at", "N/A"),
                    "url": release.get("html_url", "N/A"),
                }
            )
        return out

    @staticmethod
    def _normalise_assets_default(
        raw: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Map a raw GitHub/Gitea/Forgejo release object to the normalised asset
        list.

        The tags endpoint returns a single release object; its ``assets`` array
        is mapped to ``{name, url, size}`` entries. Assets without a download
        URL are skipped.

        :param raw: Single-element list containing the release object (as
                    returned by :meth:`_request`).
        :returns:   Normalised asset dicts.
        """
        release = raw[0] if isinstance(raw, list) and raw else {}
        assets = release.get("assets", []) or []
        return [
            {
                "name": asset.get("name"),
                "url": asset.get("browser_download_url"),
                "size": asset.get("size"),
            }
            for asset in assets
            if asset.get("browser_download_url")
        ]
