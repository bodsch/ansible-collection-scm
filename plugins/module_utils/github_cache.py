import json
from pathlib import Path
from typing import Dict, List, Optional, Union

from ansible_collections.bodsch.core.plugins.module_utils.cache.cache_valid import (
    cache_valid,
)
from ansible_collections.bodsch.core.plugins.module_utils.directory import (
    create_directory,
)


class GitHubCache:

    def __init__(self, module, cache_dir: str, cache_file: str, cache_minutes: int):

        self.module = module
        # self.module.log(msg=f"GitHubCache::__init__({cache_dir}, {cache_file}, {cache_minutes})")

        self.cache_dir = Path(cache_dir)
        self.cache_file = cache_file
        self.cache_minutes = cache_minutes

        create_directory(self.cache_dir)

    def cache_path(self, filename: str) -> Path:
        """
        Gibt den vollständigen Pfad zu einer Cache-Datei zurück,
        basierend auf `self.cache_dir` und `filename`.
        """
        # self.module.log(msg=f"GitHubCache::cache_path(filename={filename})")

        if not self.cache_dir:
            # Falls jemand `get_releases()` o.ä. aufruft, ohne `enable_cache()` vorher,
            # kehren wir hier einfach mit einem Pfad zurück, der später nicht existiert.
            return Path(filename)

        return self.cache_dir / filename

    def cached_data(self, cache_path: Path) -> Optional[Union[List, Dict]]:
        """
        Liest eine Cache-Datei, wenn sie existiert und noch gültig ist.
        Gibt deren Inhalt (aus JSON) zurück oder None, falls kein gültiger Cache vorliegt.
        """
        # self.module.log(msg=f"GitHubCache::cached_data(cache_path={cache_path})")

        if not self.cache_dir:
            return None

        # Prüfe mit cache_valid: Gibt False zurück, wenn die Datei existiert und jünger als cache_minutes ist.
        is_still_valid = not cache_valid(
            self.module, str(cache_path), self.cache_minutes, True
        )

        # _valid = "not " if not is_still_valid else ""
        # self.module.log(msg=f" - cache is {_valid}valid.")

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

    def write_cache(self, cache_path: Path, data):
        """
        Schreibt `data` als JSON in die Cache-Datei `cache_path`, falls Cache aktiviert.
        """
        # self.module.log(msg=f"GitHubCache::write_cache(cache_path={cache_path})")

        if not self.cache_dir:
            return

        try:
            with cache_path.open("w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except OSError as e:
            self.module.log(msg=f"Fehler beim Schreiben der Cache-Datei: {e}")
