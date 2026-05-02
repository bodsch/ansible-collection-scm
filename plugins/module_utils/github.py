"""
github.py
=========

Ansible module utility providing a high-level Python wrapper around the
GitHub REST API v3 (https://api.github.com).

Intended for use within Ansible collections as a ``module_utils`` helper.
Handles authentication, transparent pagination, resilient HTTP retries,
rate-limit detection, optional file-system caching, and checksum retrieval.

Typical usage inside an Ansible module
---------------------------------------
::

    from ansible_collections.bodsch.scm.plugins.module_utils.github import GitHub

    gh = GitHub(module, owner="prometheus", repository="alertmanager",
                auth={"token": "ghp_..."})
    gh.architecture(system="linux", architecture="amd64")
    gh.enable_cache(cache_minutes=60)

    status, releases, error = gh.get_releases(count=20)

Dependencies
------------
- ``requests`` / ``urllib3`` — HTTP layer with retry support
- ``packaging``              — SemVer comparison (``packaging.version``)
- ``GitHubCache``            — file-system cache helper (module_utils)
- ``ReleaseFinder``          — latest-release detection helper (module_utils)

:author:  Bodo Schulz <bodo@boone-schulz.de>
:license: Apache-2.0
"""

import re
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union

import requests
from ansible_collections.bodsch.scm.plugins.module_utils.github_cache import GitHubCache
from ansible_collections.bodsch.scm.plugins.module_utils.release_finder import (
    ReleaseFinder,
)
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


class GitHub:
    """
    High-level wrapper for the GitHub REST API v3.

    Provides methods to query releases, tags, and release assets for a single
    repository.  All network calls go through :meth:`_get_request`, which
    handles automatic pagination, exponential-backoff retries, and rate-limit
    detection.

    Results are optionally cached on disk via :class:`GitHubCache` to avoid
    exhausting the unauthenticated rate limit (60 req/h) during repeated
    Ansible runs.

    Attributes
    ----------
    module : AnsibleModule
        The calling Ansible module instance, used for logging.
    base_api_url : str
        Root URL of the GitHub REST API (``https://api.github.com``).
    headers : dict
        HTTP headers sent with every request.  Automatically extended with an
        ``Authorization`` header when a token is provided.
    github_owner : str
        Repository owner / organisation (e.g. ``"prometheus"``).
    github_repository : str
        Repository name (e.g. ``"alertmanager"``).
    system : str
        Target operating system, set via :meth:`architecture`
        (e.g. ``"linux"``).
    architecture : str
        Target CPU architecture, set via :meth:`architecture`
        (e.g. ``"amd64"``).
    gh_cache : GitHubCache
        Cache helper instance, initialised by :meth:`enable_cache`.
    """

    module = None

    def __init__(
        self, module: any, owner: str, repository: str, auth: Optional[dict] = None
    ):
        """
        Initialise the GitHub client.

        Sets up base URL, default Accept header, optional token authentication,
        and compiles the URL-parsing regex.  Cache and architecture must be
        configured separately via :meth:`enable_cache` and :meth:`architecture`.

        :param module:     Ansible module instance (used for logging).
        :param owner:      GitHub owner or organisation name.
        :param repository: GitHub repository name.
        :param auth:       Optional dict with key ``"token"`` containing a
                           GitHub Personal Access Token (PAT) or fine-grained
                           token.  Raises the authenticated rate limit from
                           60 to 5 000 requests per hour.
        """
        self.module = module

        self.gh_auth_token: Optional[str] = None

        self.base_api_url = "https://api.github.com"
        self.headers: Dict[str, str] = {"Accept": "application/vnd.github.v3+json"}

        self.cache_dir: Optional[Path] = None
        self.cache_minutes: int = 0

        # Compiled regex to extract owner/repo from a full GitHub URL
        self.github_url_re = re.compile(
            r"https://.*github\.com/([^/\s]+)/([^/\s]+)(?:/.*)?"
        )
        self.github_owner = owner
        self.github_repository = repository

        if auth:
            self.gh_auth_token = auth.get("token", None)

            if self.gh_auth_token:
                self.headers["Authorization"] = f"token {self.gh_auth_token}"

    # ------------------------------------------------------------------------------------------
    # Configuration

    def authentication(self, token: Optional[str] = None):
        """
        Set or update the GitHub Personal Access Token after instantiation.

        When called, the ``Authorization`` header is added or replaced for all
        subsequent requests.  Has no effect when *token* is ``None`` or empty.

        :param token: GitHub PAT or fine-grained token.
        """
        if token:
            self.gh_auth_token = token
            self.headers["Authorization"] = f"token {token}"

    def enable_cache(self, cache_file: str = None, cache_minutes: int = 60):
        """
        Activate file-system caching for API responses.

        Must be called before any ``get_*`` method.  Creates a
        :class:`GitHubCache` instance pointing to::

            ~/.cache/ansible/github/<owner>/<repository>/

        :param cache_file:    Optional explicit cache filename.  If omitted,
                              each method uses its own default filename.
        :param cache_minutes: Maximum age of cached data in minutes before it
                              is considered stale and re-fetched.  Defaults to
                              60.
        """
        cache_directory = (
            f"{Path.home()}/.cache/ansible/github/"
            f"{self.github_owner}/{self.github_repository}"
        )
        self.cache_file = cache_file

        self.gh_cache = GitHubCache(
            module=self.module,
            cache_dir=cache_directory,
            cache_file=cache_file,
            cache_minutes=cache_minutes,
        )

    def architecture(self, system: str, architecture: str):
        """
        Set the target platform used for asset URL matching.

        Both values are stored as instance attributes and referenced by
        :meth:`get_checksum_asset` and :meth:`checksum` when filtering
        platform-specific artefacts.

        :param system:       Operating system string, lowercase
                             (e.g. ``"linux"``, ``"darwin"``).
        :param architecture: CPU architecture string
                             (e.g. ``"amd64"``, ``"arm64"``).
        """
        self.system = system
        self.architecture = architecture

    # ------------------------------------------------------------------------------------------
    # Public API

    def get_releases(self, count: int = 10) -> Tuple[int, List[Dict], Optional[str]]:
        """
        Fetch up to *count* releases for the configured repository.

        Results are normalised to a list of dicts with keys
        ``name``, ``tag_name``, ``published_at``, and ``url``.
        The response is written to ``releases.json`` in the cache directory
        (or the filename passed to :meth:`enable_cache`) and served from cache
        on subsequent calls within the configured TTL.

        .. note::
            GitHub caps ``per_page`` at 100.  Values above 100 are silently
            clamped.  Pagination is enabled so that *count* up to 100 is
            retrieved in a single page.

        :param count: Maximum number of releases to return (default: 10,
                      max: 100).
        :returns:     ``(status_code, releases, error)`` where *releases* is a
                      list of dicts and *error* is ``None`` on success.
        """
        cache_filename = self.cache_file or "releases.json"
        cache_path = self.gh_cache.cache_path(cache_filename)

        cached = self.gh_cache.cached_data(cache_path)
        if cached is not None:
            return (200, cached, None)

        api_url = (
            f"{self.base_api_url}/repos/"
            f"{self.github_owner}/{self.github_repository}/releases"
        )
        params = {"per_page": min(count, 100)}

        status_code, releases, error = self._get_request(
            url=api_url,
            params=params,
            stream=False,
            paginate=True,
            expect_json=True,
        )

        if status_code != 200:
            self.module.log(f"ERROR: {error}")
            return (status_code, [], error)

        result = [
            {
                "name": r.get("name", "N/A"),
                "tag_name": r.get("tag_name", "N/A"),
                "published_at": r.get("published_at", "N/A"),
                "url": r.get("html_url", "N/A"),
            }
            for r in releases
        ]

        self.gh_cache.write_cache(cache_path, result)
        return (status_code, result, None)

    def get_tags(self, count: int = 10) -> Tuple[int, List[Dict], Optional[str]]:
        """
        Fetch up to *count* Git tags for the configured repository.

        Uses the ``/tags`` endpoint instead of ``/releases``.  Only the
        ``name`` field is retained per tag.  Pagination is intentionally
        disabled — only the first page (up to *count* entries) is returned.
        Results are cached in ``tags.json``.

        :param count: Maximum number of tags to return (default: 10,
                      max: 100).
        :returns:     ``(status_code, tags, error)`` where *tags* is a list of
                      dicts with key ``"name"`` and *error* is ``None`` on
                      success.
        """
        cache_filename = self.cache_file or "tags.json"
        cache_path = self.gh_cache.cache_path(cache_filename)

        cached = self.gh_cache.cached_data(cache_path)
        if cached is not None:
            return (200, cached, None)

        api_url = (
            f"{self.base_api_url}/repos/"
            f"{self.github_owner}/{self.github_repository}/tags"
        )
        params = {"per_page": min(count, 100)}

        status_code, releases, error = self._get_request(
            url=api_url,
            params=params,
            stream=False,
            paginate=False,
            expect_json=True,
        )

        if status_code != 200:
            self.module.log(f"ERROR: {error}")
            return (status_code, [], error)

        result = [{"name": r.get("name", "N/A")} for r in releases]

        self.gh_cache.write_cache(cache_path, result)
        return (status_code, result, None)

    def get_all_releases(self, repo_url: str) -> Tuple[int, List[Dict], Optional[str]]:
        """
        Fetch **all** releases including their download asset URLs.

        Iterates through every pagination page (100 releases per page) of the
        GitHub ``/releases`` endpoint and collects the ``browser_download_url``
        of every asset per release.

        Each entry in the returned list has the shape::

            {
                "name":          str,   # release title
                "tag_name":      str,   # git tag
                "published_at":  str,   # ISO-8601 timestamp
                "url":           str,   # HTML URL of the release page
                "download_urls": list,  # list of asset download URLs
            }

        Results are cached in ``release_artefacts.json``.

        :param repo_url: Full GitHub repository URL
                         (e.g. ``"https://github.com/owner/repo"``).
                         Currently only used for log messages; owner and
                         repository are taken from the constructor.
        :returns:        ``(status_code, releases, error)`` where *releases* is
                         a list of release dicts and *error* is ``None`` on
                         success.
        """
        cache_filename = "release_artefacts.json"
        cache_path = self.gh_cache.cache_path(cache_filename)

        cached = self.gh_cache.cached_data(cache_path)
        if cached is not None:
            return (200, cached, None)

        api_url = (
            f"{self.base_api_url}/repos/"
            f"{self.github_owner}/{self.github_repository}/releases"
        )
        params = {"per_page": 100}

        status_code, releases, error = self._get_request(
            url=api_url, params=params, stream=False, paginate=True, expect_json=True
        )

        if status_code != 200:
            self.module.log(f"ERROR: {error}")
            return (status_code, [], error)

        all_releases = []
        for release in releases:
            try:
                assets = release.get("assets", [])
                download_urls = [
                    x.get("browser_download_url")
                    for x in assets
                    if x.get("browser_download_url")
                ]

                filtered_release = {
                    "name": release.get("name", "N/A"),
                    "tag_name": release.get("tag_name", "N/A"),
                    "published_at": release.get("published_at", "N/A"),
                    "url": release.get("html_url", "N/A"),
                    "download_urls": download_urls,
                }
                all_releases.append(filtered_release)

            except Exception as e:
                self.module.log(f"Error processing release entry: {e}")
                continue

        self.gh_cache.write_cache(cache_path, all_releases)
        return (status_code, all_releases, None)

    def latest_published(self, releases: list = [], filter_elements: list = []) -> dict:
        """
        Return the release with the highest semantic version from *releases*.

        Delegates to :class:`ReleaseFinder` with ``mode="version"``.
        Releases whose ``name`` or ``tag_name`` match any keyword in
        *filter_elements* (case-insensitive) are excluded before evaluation.

        :param releases:        List of release dicts as returned by
                                :meth:`get_releases` or :meth:`get_all_releases`.
        :param filter_elements: Optional list of substrings to exclude
                                (e.g. ``["beta", "rc", "preview"]``).
        :returns:               The release dict with the highest SemVer, or
                                ``None`` if no valid candidates remain.
        """
        rf = ReleaseFinder(module=self.module, releases=releases)
        rf.set_exclude_keywords(keywords=filter_elements)
        return rf.find_latest(mode="version")

    def latest_tag(self, tags: list = [], filter_elements: list = []) -> dict:
        """
        Return the tag dict with the highest semantic version from *tags*.

        Uses ``packaging.version.parse`` for comparison so pre-release suffixes
        are handled correctly.  *filter_elements* is accepted for API symmetry
        with :meth:`latest_published` but is not yet applied.

        :param tags:            List of tag dicts as returned by
                                :meth:`get_tags`, each containing at least a
                                ``"name"`` key.
        :param filter_elements: Reserved for future keyword-based filtering.
        :returns:               The tag dict whose ``"name"`` represents the
                                highest version.
        :raises ValueError:     If *tags* is empty.
        """
        from packaging import version

        return max(tags, key=lambda d: version.parse(d["name"]))

    def release_exists(self, tag: str) -> bool:
        """
        Check whether a release with the given *tag* exists in the repository.

        Fetches all releases via :meth:`get_all_releases` and delegates
        version matching to :meth:`_filter_by_semver`.  A leading ``"v"`` in
        *tag* is stripped before comparison so ``"v2.3.0"`` and ``"2.3.0"``
        are treated identically.

        :param tag: Git tag to look up (with or without leading ``"v"``).
        :returns:   List of matching release dicts (truthy if found, empty list
                    if not found or on API error).
        """
        repo_url = f"https://github.com/{self.github_owner}/{self.github_repository}"
        status_code, gh_result, error = self.get_all_releases(repo_url)

        if status_code == 200:
            norm_tag = tag.lstrip("v")
            return self._filter_by_semver(gh_result, norm_tag)

        return []

    def download_checksum(self, url: str, filename: str) -> None:
        """
        Download a plain-text checksum file and persist it as a JSON cache.

        The file is fetched as plain text (not streamed) and stored line-by-line
        as a JSON array via :class:`GitHubCache`.  This format is expected by
        :meth:`checksum`.

        :param url:      Direct download URL of the checksum file.
        :param filename: Destination path (within the cache directory) where
                         the JSON-encoded line list is written.
        """
        dest = Path(filename)
        self._download_file(url, dest, stream=False)

    def get_checksum_asset(self, tag: str) -> Optional[Dict]:
        """
        Find the first checksum asset for a given release tag.

        Inspects all assets of the release identified by *tag* and returns the
        first one whose filename contains any of the keywords
        ``["sha256", "sha512", "checksum", "sum"]``.

        A secondary, more specific match (tag + system + architecture +
        keyword) is evaluated after the primary keyword-only match.

        :param tag: Git tag of the release to inspect (with or without ``"v"``).
        :returns:   Dict with keys ``"name"``, ``"url"``, and ``"size"`` for
                    the first matching asset, or ``None`` if no checksum asset
                    is found or if the release does not exist.
        """
        status_code, releases, error = self._release_assets(tag)

        if status_code != 200:
            return None

        normalized_tag = tag.lstrip("v").lower()
        keywords = ["sha256", "sha512", "checksum", "sum"]

        for asset in releases:
            name_lower = asset["name"].lower()

            # Primary match: any checksum keyword present in the asset name
            if any(kw in name_lower for kw in keywords):
                self.module.log(msg=f"  → Checksum asset found: {asset['name']}")
                return asset

            # Secondary match: tag + platform + architecture + keyword
            if (
                normalized_tag in name_lower
                and self.system in name_lower
                and self.architecture in name_lower
                and any(kw in name_lower for kw in keywords)
            ):
                self.module.log(msg=f"  → Checksum asset found: {asset['name']}")
                return asset

        return None

    def checksum(self, repo: str, filename: str):
        """
        Look up a checksum hash for a platform-specific artefact from a cached
        checksum file.

        Reads the cached line list written by :meth:`download_checksum` and
        searches for a line matching ``<repo>.*<system>.*<architecture>``.
        If exactly one line matches, the hash (first whitespace-delimited token)
        is extracted and returned.  Falls back to the single-entry case where
        the file contains only one hash line.

        :param repo:     Repository or artefact name used as the first segment
                         of the search pattern.
        :param filename: Cache filename (relative to the cache directory) as
                         passed to :meth:`download_checksum`.
        :returns:        ``(raw_lines, checksum_hash)`` where *raw_lines* is
                         the full list of cached lines and *checksum_hash* is
                         the extracted hash string, or ``([], None)`` when the
                         cache is empty or no match is found.
        """
        cache_file = self.gh_cache.cache_path(filename)
        cached_data = self.gh_cache.cached_data(cache_file)

        if cached_data:
            checksum = [
                x
                for x in cached_data
                if re.search(rf".*{repo}.*{self.system}.*{self.architecture}.*", x)
            ]

            if isinstance(checksum, list) and len(checksum) == 1:
                checksum = checksum[0]
            else:
                # Single-entry fallback: checksum file contains only one hash
                if isinstance(cached_data, list) and len(cached_data) == 1:
                    _chk = cached_data[0].split(" ")
                    if len(_chk) == 1:
                        checksum = _chk[0]

            if isinstance(checksum, str):
                checksum = checksum.split(" ")[0]

            return (cached_data, checksum)

        return ([], None)

    # ------------------------------------------------------------------------------------------
    # Private API

    def _get_request(
        self,
        url: str,
        params: Optional[dict] = None,
        stream: bool = False,
        paginate: bool = True,
        expect_json: bool = True,
    ) -> Tuple[int, Union[List[dict], str, requests.Response], Optional[str]]:
        """
        Execute a resilient HTTP GET request against the GitHub API.

        Features:

        * **Retry** — up to 3 attempts with exponential backoff (factor 1 s)
          on HTTP 429, 500, 502, 503, 504.
        * **Pagination** — follows ``Link: <url>; rel="next"`` headers
          automatically when *paginate* is ``True``, accumulating all pages
          into a single list.
        * **Rate-limit detection** — returns HTTP 429 immediately when
          ``X-RateLimit-Remaining`` reaches 0, including the wait time in the
          error message.
        * **Flexible response modes** — returns parsed JSON (list), plain text,
          or a raw streaming :class:`requests.Response` depending on
          *expect_json* and *stream*.

        :param url:         Full request URL.
        :param params:      Optional query parameters dict (only sent on the
                            first page request; cleared for subsequent pages).
        :param stream:      If ``True``, the response body is not decoded and
                            the raw :class:`requests.Response` is returned
                            (binary download).  Only meaningful when
                            *expect_json* is ``False``.
        :param paginate:    If ``True``, all pages are fetched and merged.
                            Set to ``False`` when only the first page is needed
                            (e.g. :meth:`get_tags`).
        :param expect_json: If ``True`` (default), the response body is decoded
                            as JSON and returned as a list.  If ``False``,
                            returns raw text or a streaming response.
        :returns:           ``(status_code, data, error)`` where:

                            * *status_code* is the HTTP status (or 419 for
                              network/parse errors),
                            * *data* is a list of dicts, a text string, or a
                              :class:`requests.Response` object,
                            * *error* is ``None`` on success or a human-readable
                              error string on failure.
        """
        session = requests.Session()
        retry_strategy = Retry(
            total=3,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["GET"],
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("https://", adapter)

        headers = self.headers.copy()
        result: List[dict] = []
        error = None

        while url:
            try:
                response = session.get(
                    url, headers=headers, params=params, stream=stream, timeout=15
                )

                self.module.log(msg=f"- response: {response.status_code}")

                # Detect exhausted rate limit before raise_for_status()
                if (
                    response.status_code == 403
                    and "X-RateLimit-Remaining" in response.headers
                ):
                    remaining = int(response.headers["X-RateLimit-Remaining"])
                    if remaining == 0:
                        reset_time = int(response.headers.get("X-RateLimit-Reset", 0))
                        wait_seconds = max(reset_time - int(time.time()), 1)
                        error = f"Rate limit exceeded. Retry in {wait_seconds} seconds."
                        self.module.log(error)
                        return (429, [], error)

                response.raise_for_status()

                # Non-JSON responses (file downloads)
                if not expect_json:
                    if stream:
                        return (200, response, None)
                    else:
                        return (200, response.text, None)

                # Normalise single-object responses to a list for uniform handling
                json_data = response.json()
                if not isinstance(json_data, list):
                    json_data = [json_data]
                result.extend(json_data)

                # Follow pagination via Link header
                if not paginate:
                    break

                link_header = response.headers.get("Link", "")
                next_url = None
                for link in link_header.split(","):
                    if 'rel="next"' in link:
                        next_url = link[link.find("<") + 1 : link.find(">")]
                        break

                if next_url:
                    url = next_url
                    params = None  # query params only on first request
                else:
                    break

            except requests.exceptions.RequestException as e:
                error = f"Request failed: {e}"
                self.module.log(error)
                return (419, [], error)
            except ValueError as e:
                error = f"Error parsing the JSON: {e}"
                self.module.log(error)
                return (419, [], error)

        return (200, result, None)

    def _filter_by_semver(self, entries: list, version: str) -> List[Dict]:
        """
        Filter *entries* to those whose version matches *version* exactly.

        Both ``tag_name`` and ``name`` fields are inspected.  A leading ``"v"``
        is stripped from each before parsing so ``"v2.3.0"`` and ``"2.3.0"``
        are considered equal.  Entries whose version string cannot be parsed as
        a valid PEP 440 / SemVer version are silently skipped.

        :param entries: List of release dicts (as returned by
                        :meth:`get_all_releases`).
        :param version: Target version string without leading ``"v"``
                        (e.g. ``"2.3.0"``).
        :returns:       Filtered list of matching release dicts.
        :raises ValueError: If *version* itself is not a valid version string.
        """
        from packaging.version import InvalidVersion, Version

        try:
            target = Version(version)
        except InvalidVersion:
            _msg = f"Invalid version specification: {version!r}"
            self.module.log(_msg)
            raise ValueError(_msg)

        result = []
        for e in entries:
            for key in ("tag_name", "name"):
                raw = e.get(key)
                if not raw:
                    continue
                candidate = raw.lstrip("v")
                try:
                    if Version(candidate) == target:
                        result.append(e)
                        break
                except InvalidVersion:
                    continue
        return result

    def _release_assets(self, tag: str) -> Tuple[int, List[Dict], Optional[str]]:
        """
        Fetch all downloadable assets for the release identified by *tag*.

        Results are cached in ``release_artefacts_<tag>.json``.  Each entry
        in the returned list has the shape::

            {"name": str, "url": str, "size": int}

        :param tag: Exact Git tag name used to look up the release via the
                    ``/releases/tags/<tag>`` endpoint.
        :returns:   ``(status_code, assets, error)`` where *assets* is a list
                    of asset dicts and *error* is ``None`` on success.
                    Returns ``(404, [], error)`` when the tag does not exist.
        """
        cache_filename = f"release_artefacts_{tag}.json"
        cache_path = self.gh_cache.cache_path(cache_filename)
        cached = self.gh_cache.cached_data(cache_path)

        if cached is not None:
            return (200, cached, None)

        api_url = (
            f"{self.base_api_url}/repos/"
            f"{self.github_owner}/{self.github_repository}/releases/tags/{tag}"
        )

        status_code, releases, error = self._get_request(api_url)

        if status_code != 200:
            self.module.log(
                f"Error when retrieving the release assets: {status_code} - {error}"
            )
            return (status_code, [], error)

        data = releases[0] if isinstance(releases, list) else releases
        assets = data.get("assets", [])

        result = [
            {
                "name": asset.get("name"),
                "url": asset.get("browser_download_url"),
                "size": asset.get("size"),
            }
            for asset in assets
        ]
        self.gh_cache.write_cache(cache_path, result)

        return (status_code, result, None)

    def _download_file(self, url: str, dest_path: Path, stream: bool = False) -> None:
        """
        Download a file from *url* and write it to *dest_path*.

        Two modes are supported:

        * **stream=True** (binary) — response body is written in 8 KiB chunks
          to *dest_path* in binary mode.  Suitable for large artefacts.
        * **stream=False** (text) — response body is split into non-empty
          lines and written as a JSON array via :class:`GitHubCache`.
          Required for checksum files consumed by :meth:`checksum`.

        :param url:       Direct download URL.
        :param dest_path: :class:`pathlib.Path` destination.
        :param stream:    ``True`` for binary streaming, ``False`` (default)
                          for text/JSON line-list storage.
        :raises Exception: When the HTTP response status is not 200.
        """
        status_code, content, error = self._get_request(
            url, stream=stream, expect_json=False
        )

        if status_code != 200:
            raise Exception(f"Error downloading the file: {status_code}")

        if stream:
            with dest_path.open("wb") as f:
                for chunk in content.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
        else:
            lines = [line for line in content.splitlines() if line.strip()]
            self.gh_cache.write_cache(dest_path, lines)

    # ------------------------------------------------------------------------------------------
    # Deprecated / legacy methods

    def get_releases_old(
        self, repo_url: str, count: int = 10
    ) -> Union[List[Dict], Dict]:
        """
        Fetch up to *count* releases for the configured repository.

        .. deprecated::
            Use :meth:`get_releases` instead.  This method is retained for
            backwards compatibility and will be removed in a future version.

        :param repo_url: Full GitHub repository URL (used only for logging).
        :param count:    Maximum number of releases to return (max: 500 —
                         note: GitHub caps ``per_page`` at 100).
        :returns:        ``(status_code, releases, error)``
        """
        self.module.log(msg=f"GitHub::get_releases(repo_url={repo_url}, count={count})")

        cache_filename = self.cache_file or "releases.json"
        cache_path = self.gh_cache.cache_path(cache_filename)

        cached = self.gh_cache.cached_data(cache_path)
        if cached is not None:
            return (200, cached, None)

        api_url = (
            f"{self.base_api_url}/repos/"
            f"{self.github_owner}/{self.github_repository}/releases"
        )
        params = {"per_page": min(count, 500)}

        status_code, releases, error = self._get_request(api_url, params=params)

        if status_code != 200:
            self.module.log(f"ERROR: {error}")
            return (status_code, [], error)

        if status_code == 200:
            result = [
                {
                    "name": r.get("name"),
                    "tag_name": r.get("tag_name"),
                    "published_at": r.get("published_at"),
                    "url": r.get("html_url"),
                }
                for r in releases
            ]
            self.gh_cache.write_cache(cache_path, result)
            return (status_code, result, None)

        elif status_code == 404:
            return (status_code, [], error)

        else:
            return (status_code, [], error)

    def get_all_releases_old(self, repo_url: str) -> List[Dict]:
        """
        Fetch all releases including asset download URLs.

        .. deprecated::
            Use :meth:`get_all_releases` instead.  This method is retained for
            backwards compatibility and will be removed in a future version.

        :param repo_url: Full GitHub repository URL (used only for logging).
        :returns:        ``(status_code, releases, error)``
        """
        self.module.log(msg=f"GitHub::get_all_releases(repo_url={repo_url})")

        cache_filename = "release_artefacts.json"
        cache_path = self.gh_cache.cache_path(cache_filename)

        cached = self.gh_cache.cached_data(cache_path)
        if cached is not None:
            return (200, cached, None)

        all_releases: List[Dict] = []

        api_url = (
            f"{self.base_api_url}/repos/"
            f"{self.github_owner}/{self.github_repository}/releases"
        )

        try:
            status_code, releases, error = self._get_request(api_url)

            if status_code != 200:
                self.module.log(f"ERROR: {error}")
                return (status_code, [], error)

            for release in releases:
                self.module.log(f"  -> {release}")
                try:
                    assets = release.get("assets", [])
                    download_urls = [x.get("browser_download_url") for x in assets]

                    filtered_release = {
                        "name": release.get("name", "N/A"),
                        "tag_name": release.get("tag_name", "N/A"),
                        "published_at": release.get("published_at", "N/A"),
                        "url": release.get("html_url", "N/A"),
                        "download_urls": download_urls,
                    }

                    all_releases.append(filtered_release)
                except Exception as e:
                    self.module.log(f"Error when processing a release entry: {e}")
                    continue

        except Exception as e:
            self.module.log(f"ERROR : {e}")

        self.gh_cache.write_cache(cache_path, all_releases)

        return (status_code, all_releases, None)
