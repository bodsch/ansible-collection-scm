import re
import requests
import hashlib
import json
from pathlib import Path
from typing import Optional, Tuple, Union, List, Dict

from ansible_collections.bodsch.core.plugins.module_utils.cache.cache_valid import cache_valid


class GitHub:
    """
    Utility-Klasse für GitHub-API-Aufrufe, um Releases auszulesen, Assets
    herunterzuladen und ggf. per Checksumme zu verifizieren.
    """

    def __init__(self, module):
        """
        Initialisiert die Klasse mit einem Ansible-Modulobjekt, setzt Header und Base-URL.
        """
        self.module = module
        self.module.log(msg="GitHub::__init__()")

        # Token für Authentifizierung (optional)
        self.github_token: Optional[str] = None

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

    def authentication(self, username: str = None, password: str = None, token: Optional[str] = None):
        """
        Legt einen Authorization-Header mit Personal-Access-Token an, falls gegeben.
        """
        self.module.log(msg=f"GitHub::authentication(token={'***' if token else None})")
        if token:
            self.github_token = token
            self.headers["Authorization"] = f"token {token}"

    def enable_cache(self, cache_dir: str, cache_minutes: int = 60):
        """
        Setzt `self.cache_dir` und `self.cache_minutes`. Es wird NICHT
        versucht, das Verzeichnis anzulegen, da das außen bereits sichergestellt ist.
        """
        self.module.log(msg=f"GitHub::enable_cache(cache_dir={cache_dir}, cache_minutes={cache_minutes})")

        self.cache_dir = Path(cache_dir)
        self.cache_minutes = cache_minutes

    def architecture(self, system: str, architecture: str):

        self.module.log(msg=f"GitHub::architecture({system}, {architecture})")

        self.system = system
        self.architecture = architecture

    def parse_owner_repo(self, repo_url: str) -> Tuple[str, str]:
        """
        Zerlegt eine GitHub-URL (z.B. "https://github.com/owner/repo")
        und gibt (owner, repo) zurück. Löst ValueError, wenn die URL ungültig ist.
        """
        m = self.github_url_re.match(repo_url)
        if not m:
            raise ValueError(f"Ungültige GitHub-URL: {repo_url}")
        return m.group(1), m.group(2)

    def _cache_path(self, filename: str) -> Path:
        """
        Interne Hilfsfunktion: Gibt den vollständigen Pfad zu einer Cache-Datei zurück,
        basierend auf `self.cache_dir` und `filename`. Wirft keinen Fehler, wenn
        das Verzeichnis fehlt – wir gehen davon aus, dass ein upstream-Prozess das
        Verzeichnis bereits angelegt hat.
        """
        if not self.cache_dir:
            # Falls jemand `get_releases()` o.ä. aufruft, ohne `enable_cache()` vorher,
            # kehren wir hier einfach mit einem Pfad zurück, der später nicht existiert.
            return Path(filename)
        return self.cache_dir / filename

    def _cached_data(self, cache_path: Path) -> Optional[Union[List, Dict]]:
        """
        Liest eine Cache-Datei, wenn sie existiert und noch gültig ist. Gibt deren
        Inhalt (aus JSON) zurück oder None, falls kein gültiger Cache vorliegt.
        """
        self.module.log(msg=f"GitHub::_cached_data(cache_path={cache_path})")
        if not self.cache_dir:
            return None

        # Prüfe mit cache_valid: Gibt False zurück, wenn die Datei existiert und jünger als cache_minutes ist.
        is_still_valid = not cache_valid(self.module, str(cache_path), self.cache_minutes, True)
        # self.module.log(msg=f" cache is valid: {is_still_valid}")

        if is_still_valid and cache_path.exists():
            try:
                with cache_path.open("r", encoding="utf-8") as f:
                    return json.load(f)
            except (json.JSONDecodeError, OSError):
                # Ungültiger oder nicht lesbarer Cache: lösche und ignoriere
                try:
                    cache_path.unlink()
                except OSError:
                    pass
        return None

    def _write_cache(self, cache_path: Path, data):
        """
        Schreibt `data` als JSON in die Cache-Datei `cache_path`, falls Cache aktiviert.
        """
        self.module.log(msg=f"GitHub::_write_cache(cache_path={cache_path})")
        if not self.cache_dir:
            return

        try:
            with cache_path.open("w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except OSError as e:
            self.module.log(msg=f"Fehler beim Schreiben der Cache-Datei: {e}")

    def _get_request(self, url: str, params: Optional[dict] = None, stream: bool = False) -> requests.Response:
        """
        Wrapper um requests.get, damit wir Logging zentralisieren und ggf. später
        Timeouts/Proxy-Einstellungen zentral ergänzen können.
        """
        self.module.log(msg=f"GitHub::_get_request(url={url}, params={params}, stream={stream})")
        return requests.get(url, headers=self.headers, params=params, stream=stream)

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

        owner, repo = self.parse_owner_repo(repo_url)
        cache_filename = "releases.json"
        cache_path = self._cache_path(cache_filename)

        cached = self._cached_data(cache_path)
        if cached is not None:
            return cached

        api_url = f"{self.base_api_url}/repos/{owner}/{repo}/releases"
        params = {"per_page": min(count, 100)}

        response = self._get_request(api_url, params=params)
        status = response.status_code

        if status == 200:
            releases = response.json()
            result = [
                {
                    "name": r.get("name"),
                    "tag_name": r.get("tag_name"),
                    "published_at": r.get("published_at"),
                    "url": r.get("html_url")
                }
                for r in releases
            ]
            self._write_cache(cache_path, result)
            return result

        elif status == 404:
            return {"repo": repo_url, "tag": None, "published": None}

        else:
            return {"repo": repo_url, "error": f"Fehlercode {status}"}

    def get_latest_release(self, repo_url: str) -> Dict:
        """
        Fragt das neueste Release (count=1) ab. Gibt ein Dict zurück mit:
          { "repo": repo_url, "tag": "v1.2.3" oder None, "published": ISO-Zeitstempel oder None }
        Oder im Fehlerfall z.B. {"repo": repo_url, "error": "..."}.
        """
        self.module.log(msg=f"GitHub::get_latest_release(repo_url={repo_url})")
        releases = self.get_releases(repo_url, count=1)

        if isinstance(releases, dict):
            # Fehler-Dict oder "kein Release"-Dict aus get_releases
            return releases

        if not releases:
            return {"repo": repo_url, "tag": None, "published": None}

        latest = releases[0]
        return {
            "repo": repo_url,
            "tag": latest.get("tag_name"),
            "published": latest.get("published_at")
        }

    def get_all_releases(self, repo_url: str) -> List[Dict]:
        """
        Fragt paginiert alle Releases eines Repos ab (GitHub liefert max. 100 pro Seite).
        Cacht das Ergebnis in "all_releases.json". Gibt eine Liste von Dicts zurück,
        analog zu get_releases(). Löst Exception aus, wenn ein HTTP-Fehler != 200 auftritt.
        """
        self.module.log(msg=f"GitHub::get_all_releases(repo_url={repo_url})")

        owner, repo = self.parse_owner_repo(repo_url)
        cache_filename = "all_releases.json"
        cache_path = self._cache_path(cache_filename)

        cached = self._cached_data(cache_path)
        if cached is not None:
            return cached  # Bereits aus JSON geladen

        all_releases: List[Dict] = []
        page = 1

        while True:
            params = {"per_page": 100, "page": page}
            api_url = f"{self.base_api_url}/repos/{owner}/{repo}/releases"
            response = self._get_request(api_url, params=params)
            status = response.status_code

            if status != 200:
                raise Exception(f"Fehler beim Abrufen der Releases (Seite {page}): {status}")

            data = response.json()
            if not data:
                break

            for r in data:
                download_urls = []

                assets = r.get("assets", [])
                if assets and len(assets) > 0:
                    for url in assets:
                        download_urls.append(url.get("browser_download_url"))

                all_releases.append({
                    "name": r.get("name"),
                    "tag_name": r.get("tag_name"),
                    "published_at": r.get("published_at"),
                    "url": r.get("html_url"),
                    "download_urls": download_urls
                })
            page += 1

        self._write_cache(cache_path, all_releases)
        return all_releases

    def release_assets(self, owner: str, repo: str, tag: str) -> Optional[List[Dict]]:
        """
        Liest alle Assets (Downloads) eines bestimmten Releases (per Tag) aus.
        Cacht das Ergebnis in "release_artefacts_{tag}.json". Gibt eine Liste von Dicts zurück:
          [ { "name": "<Dateiname>", "url": "<browser_download_url>", "size": <bytes> }, ... ]
        Oder None, wenn das Release (Tag) nicht existiert (HTTP 404). Löst bei anderem Fehler eine Exception aus.
        """
        self.module.log(msg=f"GitHub::release_assets(owner={owner}, repo={repo}, tag={tag})")

        cache_filename = f"release_artefacts_{tag}.json"
        cache_path = self._cache_path(cache_filename)

        cached = self._cached_data(cache_path)
        if cached is not None:
            return cached

        api_url = f"{self.base_api_url}/repos/{owner}/{repo}/releases/tags/{tag}"
        response = self._get_request(api_url)
        status = response.status_code

        if status == 200:
            data = response.json()
            assets = data.get("assets", [])
            result = [
                {
                    "name": asset.get("name"),
                    "url": asset.get("browser_download_url"),
                    "size": asset.get("size")
                }
                for asset in assets
            ]
            self._write_cache(cache_path, result)
            return result

        elif status == 404:
            return None

        else:
            raise Exception(f"Fehler beim Abrufen der Release-Assets: {status} - {response.text}")

    def release_exists(self, repo_url: str, tag: str) -> bool:
        """
        Prüft, ob für ein Repo ein Release mit dem exakten Tag existiert.
        Gibt True zurück, falls vorhanden, sonst False.
        """
        self.module.log(msg=f"GitHub::release_exists(repo_url={repo_url}, tag={tag})")
        all_rel = self.get_all_releases(repo_url)
        norm_tag = tag.lstrip("v")

        return [entry for entry in all_rel if entry.get("name", "").lstrip("v") == norm_tag]

        # for entry in all_rel:
        #     if entry.get("tag_name", "").lstrip("v") == norm_tag:
        #         return True
        # return False

    def _download_file(self, url: str, dest_path: Path, stream: bool = False) -> None:
        """
        Interne Hilfsmethode: Lädt eine Datei von URL und speichert sie als dest_path.
        Löst Exception aus, wenn HTTP-Status != 200.
        - Bei stream=True: Binär-Download via iter_content
        - Bei stream=False: Text-Download; speichert Zeilen in JSON-kompatiblem Format
        """
        self.module.log(msg=f"GitHub::_download_file(url={url}, dest={dest_path}, stream={stream})")
        response = self._get_request(url, stream=stream)
        status = response.status_code

        if status != 200:
            raise Exception(f"Fehler beim Herunterladen der Datei: {status}")

        if stream:
            with dest_path.open("wb") as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
        else:
            text = response.text
            lines = [line for line in text.splitlines() if line.strip()]
            # Hier speichern wir die Zeilenliste als JSON, damit parse_checksum_file darauf zugreifen kann.
            self._write_cache(dest_path, lines)

    def download_asset(self, url: str, filename: str) -> None:
        """
        Lädt das Asset von `url` herunter und speichert es als lokale Datei `filename`.
        Streamt binäre Daten (z.B. .zip, .tar.gz).
        """
        self.module.log(msg=f"GitHub::download_asset(url={url}, filename={filename})")
        dest = Path(filename)
        self._download_file(url, dest, stream=True)

    def download_checksum(self, url: str, filename: str) -> None:
        """
        Lädt eine Checksum-Datei (Text) von `url` herunter und speichert sie
        als JSON-Cache (Liste von Zeilen) in `filename`. (Kein reines Binär-Download.)
        """
        self.module.log(msg=f"GitHub::download_checksum(url={url}, filename={filename})")
        dest = Path(filename)
        self._download_file(url, dest, stream=False)

    def compute_hash(self, filepath: str, algorithm: str = "sha256") -> str:
        """
        Berechnet den Hash von `filepath` blockweise (standardmäßig SHA256)
        und gibt den Hex-String zurück.
        """
        self.module.log(msg=f"GitHub::compute_hash(filepath={filepath}, algorithm={algorithm})")
        hasher = hashlib.new(algorithm)
        block_size = 65536  # 64 KiB
        with open(filepath, "rb") as f:
            while (chunk := f.read(block_size)):
                hasher.update(chunk)
        return hasher.hexdigest()

    def parse_checksum_file(self, checksum_path: str, target_filename: str) -> str:
        """
        Liest eine Checksum-Datei (z. B. "checksums.txt"), die im Format
            "<hexhash>  <Dateiname>"
        vorliegt. Sucht nach `target_filename` in der zweiten Spalte
        und gibt den zugehörigen Hex-Hash zurück. Löst ValueError, falls keine passende Zeile.
        """
        self.module.log(msg=f"GitHub::parse_checksum_file({checksum_path}, {target_filename})")
        with open(checksum_path, "r", encoding="utf-8") as f:
            for line in f:
                parts = line.strip().split()
                if len(parts) >= 2:
                    hexhash, dateiname = parts[0], parts[1]
                    if dateiname == target_filename:
                        return hexhash
        raise ValueError(f"Kein Eintrag für '{target_filename}' in {checksum_path} gefunden.")

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
                normalized_tag in name_lower and
                self.system in name_lower and
                self.architecture in name_lower and
                any(kw in name_lower for kw in keywords)
            )

            if name_matches:
                self.module.log(msg=f"  → Gefundenes Checksum-Asset: {asset['name']}")
                return asset

        return None

    def has_checksum_file(self, owner: str, repo: str, tag: str) -> bool:
        """
        Gibt True zurück, falls unter den Release-Assets ein Asset-Name existiert,
        das einen der Begriffe ["sha256", "sha512", "checksum", "sum"] enthält.
        Sonst False.
        """
        self.module.log(msg=f"GitHub::has_checksum_file(owner={owner}, repo={repo}, tag={tag})")
        assets = self.release_assets(owner, repo, tag)
        if not assets:
            return False

        keywords = ["sha256", "sha512", "checksum", "sum"]
        for a in assets:
            if any(kw in a["name"].lower() for kw in keywords):
                return True
        return False

    def verify_release(self, repo_url: str, tag: str, algorithm: str = "sha256") -> bool:
        """
        Lädt von einem Release (owner/repo@tag)
          1. die Checksum-Datei
          2. das Haupt-Asset (z.B. .zip/.tar.gz)
        herunter, berechnet lokal den Hash vom Asset und vergleicht mit dem
        Hash aus der Checksum-Datei. Gibt True zurück, wenn beide übereinstimmen,
        sonst False. Löst Exceptions, falls Assets/Checksum-Datei fehlen.
        """
        self.module.log(msg=f"GitHub::verify_release(repo_url={repo_url}, tag={tag}, algorithm={algorithm})")
        owner, repo = self.parse_owner_repo(repo_url)

        assets = self.release_assets(owner, repo, tag)
        if assets is None:
            raise RuntimeError(f"Release {owner}/{repo}@{tag} nicht gefunden.")

        checksum_asset = None
        main_asset = None
        for a in assets:
            name_lower = a["name"].lower()
            if (algorithm in name_lower) or (".sha" in name_lower) or ("checksum" in name_lower):
                checksum_asset = a
            elif main_asset is None:
                main_asset = a

        if checksum_asset is None:
            raise RuntimeError(f"Keine Checksum-Datei für {owner}/{repo}@{tag} gefunden.")
        if main_asset is None:
            raise RuntimeError(f"Kein Haupt-Asset für {owner}/{repo}@{tag} gefunden.")

        checksum_filename = checksum_asset["name"]
        asset_filename = main_asset["name"]
        checksum_url = checksum_asset["url"]
        asset_url = main_asset["url"]

        # 2. Lade beides herunter
        self.download_checksum(checksum_url, checksum_filename)
        self.download_asset(asset_url, asset_filename)

        # 3. Berechne lokalen Hash
        local_hash = self.compute_hash(asset_filename, algorithm)

        # 4. Lese erwarteten Hash aus Checksum-Datei
        expected_hash = self.parse_checksum_file(checksum_filename, asset_filename)

        # 5. Vergleiche
        if local_hash.lower() == expected_hash.lower():
            self.module.log(msg=f"[OK] {algorithm}-Hash stimmt überein: {local_hash}")
            return True
        else:
            self.module.log(msg=f"[FEHLER] {algorithm}-Hash stimmt NICHT überein!")
            self.module.log(msg=f"  Erwartet: {expected_hash}")
            self.module.log(msg=f"  Gefunden: {local_hash}")
            return False

    def checksum(self, repo: str, filename: str):
        """
        """
        self.module.log(msg=f"GitHub::checksum(filename={filename})")

        cache_file = self._cache_path(filename)
        cached_data = self._cached_data(cache_file)

        self.module.log(msg=f" - {cached_data} {type(cached_data)}")

        if cached_data:
            checksum = [x for x in cached_data if re.search(fr".*{repo}.*{self.system}.*{self.architecture}.*", x)]
            self.module.log(msg=f" - {checksum}")

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
