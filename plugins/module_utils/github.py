
import re
import time
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from pathlib import Path
from typing import Optional, Tuple, Union, List, Dict

from ansible_collections.bodsch.scm.plugins.module_utils.github_cache import GitHubCache
from ansible_collections.bodsch.scm.plugins.module_utils.release_finder import ReleaseFinder


class GitHub:
    """
    """

    def __init__(self, module: any, owner: str, repository: str, auth: Optional[dict] = None):
        """
        Initialisiert die Klasse mit einem Ansible-Modulobjekt, setzt Header und Base-URL.
        """
        self.module = module
        # self.module.log(msg=f"GitHub::__init__(owner={owner}, repository={repository}, auth)")

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
        # self.module.log(msg=f"GitHub::authentication(token={'***' if token else None})")
        if token:
            self.gh_auth_token = token
            self.headers["Authorization"] = f"token {token}"

    def enable_cache(self, cache_file: str = None, cache_minutes: int = 60):
        """
            Instanziert den GitHubCache Helper
        """
        # self.module.log(msg=f"GitHub::enable_cache(cache_file={cache_file}, cache_minutes={cache_minutes})")

        cache_directory = f"{Path.home()}/.cache/ansible/github/{self.github_owner}/{self.github_repository}"
        self.cache_file = cache_file

        self.gh_cache = GitHubCache(
            module = self.module,
            cache_dir = cache_directory,
            cache_file = cache_file,
            cache_minutes = cache_minutes
        )

    def architecture(self, system: str, architecture: str):

        # self.module.log(msg=f"GitHub::architecture({system}, {architecture})")

        self.system = system
        self.architecture = architecture

    # ------------------------------------------------------------------------------------------
    # public API
    def get_releases(self, repo_url: str, count: int = 10) -> Tuple[int, List[Dict], Optional[str]]:
        """
        Fragt bis zu `count` Releases (max. 100) eines Repos ab.
        Cacht das Ergebnis in "releases.json" (sofern aktiviert).
        Gibt (status_code, Ergebnisliste, Fehler) zurück.
        """
        # self.module.log(msg=f"GitHub::get_releases(repo_url={repo_url}, count={count})")

        cache_filename = self.cache_file or "releases.json"
        cache_path = self.gh_cache.cache_path(cache_filename)

        cached = self.gh_cache.cached_data(cache_path)
        if cached is not None:
            return (200, cached, None)

        api_url = f"{self.base_api_url}/repos/{self.github_owner}/{self.github_repository}/releases"
        params = {
            "per_page": min(count, 100)
        }

        status_code, releases, error = self._get_request(
            url=api_url,
            params=params,
            stream=False,
            paginate=True,     # ❗ bewusst keine Pagination hier
            expect_json=True
        )

        if status_code != 200:
            self.module.log(f"ERROR: {error}")
            return (status_code, [], error)

        result = [
            {
                "name": r.get("name", "N/A"),
                "tag_name": r.get("tag_name", "N/A"),
                "published_at": r.get("published_at", "N/A"),
                "url": r.get("html_url", "N/A")
            }
            for r in releases  # [:count]
        ]

        self.gh_cache.write_cache(cache_path, result)
        return (status_code, result, None)

    def get_all_releases(self, repo_url: str) -> Tuple[int, List[Dict], Optional[str]]:
        """
        Fragt paginiert alle Releases eines Repos ab (GitHub liefert max. 100 pro Seite).
        Cacht das Ergebnis in "release_artefacts.json".
        Gibt (status_code, Datenliste, Fehler) zurück.
        """
        # self.module.log(msg=f"GitHub::get_all_releases(repo_url={repo_url})")

        cache_filename = "release_artefacts.json"
        cache_path = self.gh_cache.cache_path(cache_filename)

        cached = self.gh_cache.cached_data(cache_path)
        if cached is not None:
            return (200, cached, None)

        api_url = f"{self.base_api_url}/repos/{self.github_owner}/{self.github_repository}/releases"
        params = {"per_page": 100}  # Maximale Page-Größe von GitHub

        status_code, releases, error = self._get_request(
            url=api_url,
            params=params,
            stream=False,
            paginate=True,
            expect_json=True
        )

        if status_code != 200:
            self.module.log(f"ERROR: {error}")
            return (status_code, [], error)

        all_releases = []
        for release in releases:
            try:
                assets = release.get("assets", [])
                download_urls = [x.get("browser_download_url") for x in assets if x.get("browser_download_url")]

                filtered_release = {
                    "name": release.get("name", "N/A"),
                    "tag_name": release.get("tag_name", "N/A"),
                    "published_at": release.get("published_at", "N/A"),
                    "url": release.get("html_url", "N/A"),
                    "download_urls": download_urls
                }
                all_releases.append(filtered_release)

            except Exception as e:
                self.module.log(f"Fehler beim Verarbeiten eines Release-Eintrags: {e}")
                continue

        self.gh_cache.write_cache(cache_path, all_releases)
        return (status_code, all_releases, None)

    def latest_published(self, releases: list = [], filter_elements: list = []) -> dict:
        """
        """
        # self.module.log(msg=f"GitHub::latest_published(releases={releases}, filter_elements={filter_elements})")

        rf = ReleaseFinder(module=self.module, releases=releases)
        rf.set_exclude_keywords(keywords=filter_elements)
        latest = rf.find_latest(mode="version")

        return latest

    def release_exists(self, tag: str) -> bool:
        """
            Prüft, ob für ein Repo ein Release mit dem exakten Tag existiert.
            Gibt True zurück, falls vorhanden, sonst False.
        """
        # self.module.log(msg=f"GitHub::release_exists(tag={tag})")

        repo_url = f"https://github.com/{self.github_owner}/{self.github_repository}"
        status_code, gh_result, error = self.get_all_releases(repo_url)

        if status_code == 200:
            norm_tag = tag.lstrip("v")
            matching = self._filter_by_semver(gh_result, norm_tag)
            return matching

        return []

    def download_checksum(self, url: str, filename: str) -> None:
        """
        Lädt eine Checksum-Datei (Text) von `url` herunter und speichert sie
        als JSON-Cache (Liste von Zeilen) in `filename`. (Kein reines Binär-Download.)
        """
        # self.module.log(msg=f"GitHub::download_checksum(url={url}, filename={filename})")

        dest = Path(filename)
        self._download_file(url, dest, stream=False)

    def get_checksum_asset(self, tag: str) -> Optional[Dict]:
        """
        Gibt das erste gefundene Checksum-Asset zurück, falls unter den Release-Assets
        ein Asset-Name existiert, der eine der Begriffe ["sha256", "sha512", "checksum", "sum"] enthält.
        Ansonsten None.
        """
        # self.module.log(msg=f"GitHub::get_checksum_asset(tag={tag})")

        status_code, releases, error = self._release_assets(tag)

        if status_code != 200:
            return None

        normalized_tag = tag.lstrip("v").lower()
        keywords = ["sha256", "sha512", "checksum", "sum"]

        for asset in releases:
            name_lower = asset["name"].lower()
            name_matches = (
                any(kw in name_lower for kw in keywords)
            )

            if name_matches:
                # self.module.log(msg=f"  → Checksum asset found: {asset['name']}")
                return asset

            name_matches = (
                normalized_tag in name_lower and
                self.system in name_lower and
                self.architecture in name_lower and
                any(kw in name_lower for kw in keywords)
            )

            if name_matches:
                # self.module.log(msg=f"  → Checksum asset found: {asset['name']}")
                return asset

        return None

    def checksum(self, repo: str, filename: str):
        """
        """
        # self.module.log(msg=f"GitHub::checksum(filename={filename})")

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

            return (cached_data, checksum)

        return ([], None)

    # ------------------------------------------------------------------------------------------
    # private API
    def _get_request(
        self,
        url: str,
        params: Optional[dict] = None,
        stream: bool = False,
        paginate: bool = True,
        expect_json: bool = True
    ) -> Tuple[int, Union[List[dict], str, requests.Response], Optional[str]]:
        """
        Robuste GET-Anfrage mit:
        - Retry bei 5xx und Timeout
        - Pagination über Link-Header
        - Rate Limit Handling
        - JSON oder plain text/streaming Download
        """
        # self.module.log(msg=f"GitHub::_get_request(url={url}, params={params}, stream={stream}, paginate={paginate}, expect_json={expect_json})")

        session = requests.Session()
        retry_strategy = Retry(
            total=3,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["GET"]
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("https://", adapter)

        headers = self.headers.copy()
        result: List[dict] = []
        error = None

        while url:
            try:
                response = session.get(url, headers=headers, params=params, stream=stream, timeout=15)

                # Rate limit erreicht
                if response.status_code == 403 and "X-RateLimit-Remaining" in response.headers:
                    remaining = int(response.headers["X-RateLimit-Remaining"])
                    if remaining == 0:
                        reset_time = int(response.headers.get("X-RateLimit-Reset", 0))
                        wait_seconds = max(reset_time - int(time.time()), 1)
                        error = f"Rate limit exceeded. Retry in {wait_seconds} seconds."
                        self.module.log(error)
                        return (429, [], error)

                response.raise_for_status()

                # Wenn kein JSON erwartet wird (z. B. Datei-Download)
                if not expect_json:
                    if stream:
                        return (200, response, None)
                    else:
                        return (200, response.text, None)

                # JSON-Verarbeitung
                json_data = response.json()
                if not isinstance(json_data, list):
                    json_data = [json_data]
                result.extend(json_data)

                # Pagination prüfen
                if not paginate:
                    break

                link_header = response.headers.get("Link", "")
                next_url = None
                for link in link_header.split(","):
                    if 'rel="next"' in link:
                        next_url = link[link.find("<") + 1: link.find(">")]
                        break

                if next_url:
                    url = next_url
                    params = None  # Nur beim ersten Aufruf
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

    def _filter_by_semver(self, entries: list, version: str):
        """
        SemVer-basiertes Filtern: parst alle tag_name/name-Felder
        und vergleicht sie als Version-Objekte.
        """
        # self.module.log(msg=f"GitHub::_filter_by_semver(entries, {version})")

        from packaging.version import Version, InvalidVersion
        try:
            target = Version(version)
        except InvalidVersion:
            _msg = f"Invalid version specification: {version!r}"
            self.module.log(_msg)
            raise ValueError(_msg)

        result = []
        for e in entries:
            for key in ('tag_name', 'name'):
                raw = e.get(key)
                if not raw:
                    continue
                # 'v' am Anfang ignorieren
                candidate = raw.lstrip('v')
                try:
                    if Version(candidate) == target:
                        result.append(e)
                        break
                except InvalidVersion:
                    # z. B. "0.5-11-gb9a2814" lässt sich u.U. nicht parse-en
                    continue
        return result

    def _release_assets(self, tag: str) -> Optional[List[Dict]]:
        """
        Liest alle Assets (Downloads) eines bestimmten Releases (per Tag) aus.
        Cacht das Ergebnis in "release_artefacts_{tag}.json". Gibt eine Liste von Dicts zurück:
          [ { "name": "<Dateiname>", "url": "<browser_download_url>", "size": <bytes> }, ... ]
        Oder None, wenn das Release (Tag) nicht existiert (HTTP 404). Löst bei anderem Fehler eine Exception aus.
        """
        # self.module.log(msg=f"GitHub::_release_assets(tag={tag})")

        cache_filename = f"release_artefacts_{tag}.json"
        cache_path = self.gh_cache.cache_path(cache_filename)
        cached = self.gh_cache.cached_data(cache_path)

        if cached is not None:
            return (200, cached, None)

        api_url = f"{self.base_api_url}/repos/{self.github_owner}/{self.github_repository}/releases/tags/{tag}"

        (status_code, releases, error) = self._get_request(api_url)

        if status_code != 200:
            self.module.log(f"Error when retrieving the release assets: {status_code} - {error}")

            return (status_code, [], error)

        if isinstance(releases, list):
            data = releases[0]
        else:
            data = releases

        assets = data.get("assets", [])

        result = [
            {
                "name": asset.get("name"),
                "url": asset.get("browser_download_url"),
                "size": asset.get("size")
            }
            for asset in assets
        ]
        self.gh_cache.write_cache(cache_path, result)

        return (status_code, result, None)

    def _download_file(self, url: str, dest_path: Path, stream: bool = False) -> None:
        """
        Interne Hilfsmethode: Lädt eine Datei von URL und speichert sie als dest_path.
        Löst Exception aus, wenn HTTP-Status != 200.
        - Bei stream=True: Binär-Download via iter_content
        - Bei stream=False: Text-Download; speichert Zeilen in JSON-kompatiblem Format
        """
        # self.module.log(msg=f"GitHub::_download_file(url={url}, dest={dest_path}, stream={stream})")

        (status_code, content, error) = self._get_request(url, stream=stream, expect_json=False)

        if status_code != 200:
            raise Exception(f"Error downloading the file: {status_code}")

        if stream:
            with dest_path.open("wb") as f:
                for chunk in content.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
        else:
            lines = [line for line in content.splitlines() if line.strip()]
            # Hier speichern wir die Zeilenliste als JSON, damit parse_checksum_file darauf zugreifen kann.
            self.gh_cache.write_cache(dest_path, lines)

    # ------------------------------------------------------------------------------------------

    def get_releases_old(self, repo_url: str, count: int = 10) -> Union[List[Dict], Dict]:
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
        # self.module.log(msg=f"GitHub::get_releases(repo_url={repo_url}, count={count})")

        cache_filename = self.cache_file or "releases.json"
        cache_path = self.gh_cache.cache_path(cache_filename)

        cached = self.gh_cache.cached_data(cache_path)
        if cached is not None:
            return (200, cached, None)

        api_url = f"{self.base_api_url}/repos/{self.github_owner}/{self.github_repository}/releases"
        params = {"per_page": min(count, 500)}

        (status_code, releases, error) = self._get_request(api_url, params=params)

        if status_code != 200:
            self.module.log(f"ERROR: {error}")
            return (status_code, [], error)

        if status_code == 200:
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

    def get_all_releases_old(self, repo_url: str) -> List[Dict]:
        """
        Fragt paginiert alle Releases eines Repos ab (GitHub liefert max. 100 pro Seite).

        Cacht das Ergebnis in "release_artefacts.json".
        Gibt eine Liste von Dicts zurück, analog zu get_releases().
        """
        # self.module.log(msg=f"GitHub::get_all_releases(repo_url={repo_url})")

        cache_filename = "release_artefacts.json"
        cache_path = self.gh_cache.cache_path(cache_filename)

        cached = self.gh_cache.cached_data(cache_path)

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
                    self.module.log(f"Error when processing a release entry: {e}")
                    continue  # Weiter mit dem nächsten Eintrag

        except Exception as e:
            self.module.log(f"ERROR : {e}")
            pass

        self.gh_cache.write_cache(cache_path, all_releases)

        return (status_code, all_releases, None)
