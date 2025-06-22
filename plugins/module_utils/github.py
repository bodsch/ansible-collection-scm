
import re
import time
import json
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from pathlib import Path
from typing import Optional, Tuple, Union, List, Dict

from ansible_collections.bodsch.scm.plugins.module_utils.github_cache import GitHubCache
from ansible_collections.bodsch.scm.plugins.module_utils.release_finder import ReleaseFinder

"""
# github_releases:
        gh = GitHub(self.module)
        gh.architecture(system=self.system, architecture=self.architecture)
        gh.enable_cache(cache_dir=self.cache_directory)
        gh.authentication(username=self.github_username, password=self.github_password, token=self.github_password)

        status_code, gh_result, error = gh.get_all_releases(repo_url=self.github_url)

# github_latest:
        gh = GitHub(self.module)
        gh.enable_cache(cache_dir=self.cache_directory, cache_file=self.cache_file_name)
        gh.authentication(username=self.github_username, password=self.github_password, token=self.github_password)

        gh_releases = gh.get_releases(self.github_url)
        gh_latest_release = gh.latest_published(gh_releases)

# github_checksum:
        gh = GitHub(self.module)
        gh.architecture(system=self.system, architecture=self.architecture)
        gh.enable_cache(cache_dir=self.cache_directory)
        gh.authentication(username=self.github_username, password=self.github_password, token=self.github_password)

        release = gh.release_exists(repo_url=f"https://github.com/{self.project}/{self.repository}", tag=self.version)
        gh_checksum_data = gh.get_checksum_asset(owner=self.project, repo=self.repository, tag=self.version)
            gh.download_checksum(url, filename=cache_file_name)

        data, gh_checksum = gh.checksum(repo=self.repository, filename=cache_file_name)
"""


class GitHub:
    """
    """

    def __init__(self, module: any, owner: str, repository: str, auth: Optional[dict] = None):
        """
        Initialisiert die Klasse mit einem Ansible-Modulobjekt, setzt Header und Base-URL.
        """
        self.module = module
        self.module.log(msg=f"GitHub::__init__(owner={owner}, repository={repository}, auth)")

        # Token für Authentifizierung (optional)
        self.gh_auth_token: Optional[str] = None

        # Basis-URL und Standard-Header für GitHub API v3
        self.base_api_url = "https://api.github.com"
        self.headers: Dict[str, str] = {
            "Accept": "application/vnd.github.v3+json"
        }

        # Caching-Konfiguration (wird extern initialisiert)
        self.cache_dir: Optional[Path] = None
        self.cache_minutes: int = 0

        # Regex, um GitHub-URLs (owner/repo) zu erkennen
        self.github_url_re = re.compile(r"https://.*github\.com/([^/\s]+)/([^/\s]+)(?:/.*)?")
        self.github_owner = owner
        self.github_repository = repository

        if auth:
            self.gh_auth_token = auth.get("token", None)

            if self.gh_auth_token:
                self.headers["Authorization"] = f"token {self.gh_auth_token}"

    def authentication(self, token: Optional[str] = None):
        """
        Legt einen Authorization-Header mit Personal-Access-Token an, falls gegeben.
        """
        self.module.log(msg=f"GitHub::authentication(token={'***' if token else None})")
        if token:
            self.gh_auth_token = token
            self.headers["Authorization"] = f"token {token}"

    def enable_cache(self, cache_file: str = None, cache_minutes: int = 60):
        """
            Instanziert den GitHubCache Helper
        """
        self.module.log(msg=f"GitHub::enable_cache(cache_file={cache_file}, cache_minutes={cache_minutes})")

        cache_directory = f"{Path.home()}/.cache/ansible/github/{self.github_owner}/{self.github_repository}"
        self.cache_file = cache_file

        self.gh_cache = GitHubCache(
            module = self.module,
            cache_dir = cache_directory,
            cache_file = cache_file,
            cache_minutes = cache_minutes
        )

    def architecture(self, system: str, architecture: str):

        self.module.log(msg=f"GitHub::architecture({system}, {architecture})")

        self.system = system
        self.architecture = architecture

    # ------------------------------------------------------------------------------------------
    # public API
    def get_releases(self, repo_url: str, count: int = 10) -> Union[List[Dict], Dict]:
        """
        Fragt bis zu `count` Releases (max. 100) eines Repos ab.
        Cacht das Ergebnis in "releases.json" im cache_dir (sofern aktiviert).
        Gibt bei Erfolg eine Liste von Dicts zurück:
          [
            { "name": "...", "tag_name": "...", "published_at": "...", "url": "..." },
            ...
          ]
        Falls 404: {"repo": repo_url, "tag": None, "published": None}
        Sonst bei anderem Fehler: {"repo": repo_url, "error": "Fehlercode ..."}
        """
        self.module.log(msg=f"GitHub::get_releases(repo_url={repo_url}, count={count})")

        # owner, repo = self._parse_owner_repo(repo_url)
        cache_filename = self.cache_file or "releases.json"
        cache_path = self.gh_cache.cache_path(cache_filename)

        cached = self.gh_cache.cached_data(cache_path)
        if cached is not None:
            return (200, cached, None)

        api_url = f"{self.base_api_url}/repos/{self.github_owner}/{self.github_repository}/releases"
        params = {"per_page": min(count, 500)}

        (status_code, releases, error) = self._get_request(api_url, params=params)
        # status = response.status_code

        if status_code != 200:
            self.module.log(f"ERROR: {error}")
            return (status_code, [], error)

        if status_code == 200:
            # releases = releases  # response.json()
            result = [
                {
                    "name": r.get("name"),
                    "tag_name": r.get("tag_name"),
                    "published_at": r.get("published_at"),
                    "url": r.get("html_url")
                }
                for r in releases
            ]
            self.gh_cache.write_cache(cache_path, result)
            return (status_code, result, None)

        elif status_code == 404:
            return (status_code, [], error)

        else:
            return (status_code, [], error)

    def get_all_releases(self, repo_url: str) -> List[Dict]:
        """
        Fragt paginiert alle Releases eines Repos ab (GitHub liefert max. 100 pro Seite).

        Cacht das Ergebnis in "release_artefacts.json".
        Gibt eine Liste von Dicts zurück, analog zu get_releases().
        Löst Exception aus, wenn ein HTTP-Fehler != 200 auftritt.
        """
        self.module.log(msg=f"GitHub::get_all_releases(repo_url={repo_url})")

        # owner, repo = self._parse_owner_repo(repo_url)
        cache_filename = "release_artefacts.json"
        cache_path = self.gh_cache.cache_path(cache_filename)

        cached = self.gh_cache.cached_data(cache_path)

        self.module.log(f"cached: {cached}")

        if cached is not None:
            return (200, cached, None)

        all_releases: List[Dict] = []

        api_url = f"{self.base_api_url}/repos/{self.github_owner}/{self.github_repository}/releases"

        try:
            (status_code, releases, error) = self._get_request(api_url)

            if status_code != 200:
                self.module.log(f"ERROR: {error}")
                return (status_code, [], error)

            for release in releases:
                # self.module.log(f"  -> {release}")
                try:
                    # Manche Releases können keine Assets enthalten
                    assets = release.get("assets", [])
                    download_urls = [x.get("browser_download_url") for x in assets]

                    filtered_release = {
                        "name": release.get("name", "N/A"),
                        "tag_name": release.get("tag_name", "N/A"),
                        "published_at": release.get("published_at", "N/A"),
                        "url": release.get("html_url", "N/A"),
                        "download_urls": download_urls  # Liste von URLs
                    }

                    all_releases.append(filtered_release)
                except Exception as e:
                    self.module.log(f"Fehler beim Verarbeiten eines Release-Eintrags: {e}")
                    continue  # Weiter mit dem nächsten Eintrag

        except Exception as e:
            self.module.log(f" - ERROR : {e}")

        self.gh_cache.write_cache(cache_path, all_releases)

        self.module.log(f"= all_releases: {all_releases}")

        return (status_code, all_releases, None)
        # return all_releases

        # while True:
        #     params = {"per_page": 300, "page": page}
        #     api_url = f"{self.base_api_url}/repos/{owner}/{repo}/releases"
        #
        #     status = 0
        #
        #     try:
        #         response = self._get_request(api_url, params=params)
        #         status = response.status_code
        #
        #         self.module.log(f" - status: {status}")
        #     except Exception as e:
        #         self.module.log(f" - ERROR : {e}")
        #
        #     if status != 200:
        #         _error=f"Error when retrieving the releases (page {page}): {status}"
        #         self.module.log(_error)
        #         raise Exception(_error)
        #
        #     try:
        #         data = response.json()
        #     except Exception as e:
        #         self.module.log(f" - ERROR: {e}")
        #
        #     if not data:
        #         break
        #
        #     self.module.log(f" - data: {len(data)}")
        #
        #     for r in data:
        #         download_urls = []
        #
        #         assets = r.get("assets", [])
        #         if assets and len(assets) > 0:
        #             for url in assets:
        #                 download_urls.append(url.get("browser_download_url"))
        #
        #         all_releases.append({
        #             "name": r.get("name"),
        #             "tag_name": r.get("tag_name"),
        #             "published_at": r.get("published_at"),
        #             "url": r.get("html_url"),
        #             "download_urls": download_urls
        #         })
        #     page += 1

        self.gh_cache.write_cache(cache_path, all_releases)

        self.module.log(f"= all_releases: {all_releases}")

        return all_releases

    def latest_published(self, releases: list = []) -> dict:
        """
        """
        self.module.log(msg=f"GitHub::latest_published(releases={releases})")

        rf = ReleaseFinder(module=self.module, releases=releases)
        latest = rf.find_latest()

        return latest

    def release_exists(self, repo_url: str, tag: str) -> bool:
        """
        Prüft, ob für ein Repo ein Release mit dem exakten Tag existiert.
        Gibt True zurück, falls vorhanden, sonst False.
        """
        self.module.log(msg=f"GitHub::release_exists(repo_url={repo_url}, tag={tag})")

        all_rel = self.get_all_releases(repo_url)
        norm_tag = tag.lstrip("v")

        matching = self.filter_by_semver(all_rel, norm_tag)

        return matching

    def download_checksum(self, url: str, filename: str) -> None:
        """
        Lädt eine Checksum-Datei (Text) von `url` herunter und speichert sie
        als JSON-Cache (Liste von Zeilen) in `filename`. (Kein reines Binär-Download.)
        """
        self.module.log(msg=f"GitHub::download_checksum(url={url}, filename={filename})")

        dest = Path(filename)
        self._download_file(url, dest, stream=False)

    def get_checksum_asset(self, owner: str, repo: str, tag: str) -> Optional[Dict]:
        """
        Gibt das erste gefundene Checksum-Asset zurück, falls unter den Release-Assets
        ein Asset-Name existiert, der eine der Begriffe ["sha256", "sha512", "checksum", "sum"] enthält.
        Ansonsten None.
        """
        self.module.log(msg=f"GitHub::get_checksum_asset(owner={owner}, repo={repo}, tag={tag})")

        assets = self.release_assets(owner, repo, tag)

        if not assets:
            return None

        normalized_tag = tag.lstrip("v").lower()
        keywords = ["sha256", "sha512", "checksum", "sum"]

        for asset in assets:
            name_lower = asset["name"].lower()
            name_matches = (
                any(kw in name_lower for kw in keywords)
            )

            if name_matches:
                self.module.log(msg=f"  → Gefundenes Checksum-Asset: {asset['name']}")
                return asset

            name_matches = (
                normalized_tag in name_lower and
                self.system in name_lower and
                self.architecture in name_lower and
                any(kw in name_lower for kw in keywords)
            )

            if name_matches:
                self.module.log(msg=f"  → Gefundenes Checksum-Asset: {asset['name']}")
                return asset

        return None

    def checksum(self, repo: str, filename: str):
        """
        """
        self.module.log(msg=f"GitHub::checksum(filename={filename})")

        cache_file = self.gh_cache.cache_path(filename)
        cached_data = self.gh_cache.cached_data(cache_file)

        if cached_data:
            checksum = [x for x in cached_data if re.search(fr".*{repo}.*{self.system}.*{self.architecture}.*", x)]

            if isinstance(checksum, list) and len(checksum) == 1:
                checksum = checksum[0]
            else:
                if isinstance(cached_data, list) and len(cached_data) == 1:
                    """
                        single entry
                    """
                    _chk = cached_data[0].split(" ")
                    _len = len(_chk)

                    if _len == 1:
                        checksum = _chk[0]

            if isinstance(checksum, str):
                checksum = checksum.split(" ")[0]

            return cached_data, checksum

        return None

    # ------------------------------------------------------------------------------------------
    # private API
    # def _parse_owner_repo(self, repo_url: str) -> Tuple[str, str]:
    #     """
    #     Zerlegt eine GitHub-URL (z.B. "https://github.com/owner/repo")
    #     und gibt (owner, repo) zurück. Löst ValueError, wenn die URL ungültig ist.
    #     """
    #     m = self.github_url_re.match(repo_url)
    #     if not m:
    #         raise ValueError(f"Ungültige GitHub-URL: {repo_url}")
    #
    #     return m.group(1), m.group(2)

    def _get_request(
        self,
        url: str,
        params: Optional[dict] = None,
        stream: bool = False,
        paginate: bool = True
    ) -> Tuple[int, List[dict], Optional[str]]:
        """
        Robustere GET-Anfrage mit:
        - automatischem Retry (bei 5xx oder Timeout)
        - Rate Limit Erkennung
        - Pagination-Unterstützung
        """
        self.module.log(msg=f"GitHub::_get_request(url={url}, params={params}, stream={stream}, paginate={paginate})")

        session = requests.Session()

        retry_strategy = Retry(
            total=3,
            backoff_factor=1,  # Sekunde * 2^n Wartezeit
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["GET"]
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("https://", adapter)

        headers = self.headers.copy()
        result = []
        error = None

        while url and paginate:
            try:
                response = session.get(url, headers=headers, params=params, stream=stream, timeout=15)

                # Rate Limit erreicht
                if response.status_code == 403 and "X-RateLimit-Remaining" in response.headers:
                    remaining = int(response.headers["X-RateLimit-Remaining"])
                    if remaining == 0:
                        reset_time = int(response.headers.get("X-RateLimit-Reset", 0))
                        wait_seconds = max(reset_time - int(time.time()), 1)
                        error = f"Rate limit exceeded. Retry in {wait_seconds} seconds."
                        self.module.log(error)
                        return (429, result, error)

                response.raise_for_status()

                try:
                    data = response.json()
                    if not isinstance(data, list):
                        data = [data]
                    result.extend(data)
                except Exception as e:
                    error = f"Fehler beim Parsen des JSON: {e}"
                    self.module.log(error)
                    return (419, result, error)

                # Pagination via Link-Header
                link_header = response.headers.get("Link", "")
                next_url = None
                for link in link_header.split(","):
                    if 'rel="next"' in link:
                        next_url = link[link.find("<") + 1 : link.find(">")]
                        break

                url = next_url
                params = None  # Nur beim ersten Request verwenden

            except requests.exceptions.RequestException as e:
                error = f"Request failed: {e}"
                self.module.log(error)
                return (419, result, error)

        return (200, result, None)

    # ------------------------------------------------------------------------------------------

    def _get_request_old(self, url: str, params: Optional[dict] = None, stream: bool = False) -> requests.Response:
        """
        Wrapper um requests.get, damit wir Logging zentralisieren und ggf. später
        Timeouts/Proxy-Einstellungen zentral ergänzen können.
        """
        self.module.log(msg=f"GitHub::_get_request(url={url}, params={params}, stream={stream})")

        error = None
        result = []

        try:
            response = requests.get(url, headers=self.headers, params=params, stream=stream, timeout=20)
            response.raise_for_status()  # Löst eine Exception aus bei HTTP-Fehlern

            status_code = response.status_code

            # self.module.log(f"{response.status_code}")
            # _headers = response.headers
            # self.module.log(f"headers: {_headers}")
            # self.module.log(f"Raw response (text): {response.text}")
            # self.module.log(f"json   : {response.json()}")

            try:
                # Manuelle Dekodierung statt response.json()
                releases = json.loads(response.content.decode('utf-8'))

                self.module.log(f" - result type: {type(releases)}")

                if not isinstance(releases, list):
                    raise ValueError("Unerwartetes JSON-Format: Keine Liste von Releases")

                return (status_code, releases, error)

            except (ValueError, TypeError, json.JSONDecodeError) as e:
                error = f"Error processing the JSON data. {e}"
                self.module.log(error)
                return (419, result, error)

        except Exception as e:
            self.module.log(e)
            return (419, result, e)
            # raise Exception(_error)

    # ------------------------------------------------------------------------------------------
