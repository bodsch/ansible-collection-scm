"""
github_cache.py
===============

File-system cache helper for GitHub API responses used within Ansible
module utilities.

Responses from the GitHub REST API are serialised as JSON and stored in a
per-repository directory under ``~/.cache/ansible/github/<owner>/<repo>/``.
Each logical dataset (releases list, tag list, individual release assets, …)
gets its own cache file.  A configurable TTL (in minutes) controls how long
a cached file is considered valid before a live API call is triggered.

The TTL check is delegated to
``ansible_collections.bodsch.core.plugins.module_utils.cache.cache_valid``,
which compares the file's modification time against the current wall-clock
time.

Typical usage
-------------
::

    from github_cache import GitHubCache

    cache = GitHubCache(
        module=ansible_module,
        cache_dir="/home/user/.cache/ansible/github/prometheus/alertmanager",
        cache_file=None,          # individual callers choose their filenames
        cache_minutes=60,
    )

    path = cache.cache_path("releases.json")
    data = cache.cached_data(path)   # None → cache miss or expired

    if data is None:
        data = fetch_from_api()
        cache.write_cache(path, data)

:license: Apache-2.0
"""

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
    """
    Thin file-system cache layer for GitHub API JSON responses.

    Each instance is bound to a single cache directory and a TTL value.
    The directory is created automatically on instantiation if it does not
    already exist.

    All data is stored as pretty-printed JSON (``indent=2``, UTF-8) so that
    cache files can be inspected manually during debugging.

    Attributes
    ----------
    module : AnsibleModule
        Ansible module instance used for logging.
    cache_dir : pathlib.Path
        Absolute path to the cache directory.
    cache_file : str or None
        Optional default cache filename supplied at construction time.
        Not used internally — callers pass explicit filenames to each method.
    cache_minutes : int
        Maximum age of a cache file in minutes before it is treated as stale.
    """

    def __init__(self, module, cache_dir: str, cache_file: str, cache_minutes: int):
        """
        Initialise the cache and ensure the cache directory exists.

        :param module:        Ansible module instance (used for logging).
        :param cache_dir:     Absolute or home-relative path to the directory
                              where cache files are stored.  Created
                              automatically via ``create_directory`` if absent.
        :param cache_file:    Default cache filename (currently informational
                              only; callers supply filenames explicitly).
        :param cache_minutes: TTL in minutes.  A value of ``0`` effectively
                              disables caching (every call is treated as a
                              miss) because any existing file would immediately
                              be considered stale.
        """
        self.module = module
        self.cache_dir = Path(cache_dir)
        self.cache_file = cache_file
        self.cache_minutes = cache_minutes

        create_directory(self.cache_dir)

    def cache_path(self, filename: str) -> Path:
        """
        Build the full path for a cache file inside the cache directory.

        When :attr:`cache_dir` is falsy (e.g. ``None`` or an empty string),
        a bare :class:`pathlib.Path` of *filename* is returned.  This keeps
        callers from crashing when :meth:`~GitHub.enable_cache` was not called
        before a ``get_*`` method, at the cost of the path being unlikely to
        exist — the subsequent :meth:`cached_data` call will return ``None``
        and trigger a live fetch.

        :param filename: Cache file name (e.g. ``"releases.json"``).
        :returns:        ``cache_dir / filename`` as a :class:`pathlib.Path`,
                         or ``Path(filename)`` when ``cache_dir`` is unset.
        """
        if not self.cache_dir:
            return Path(filename)

        return self.cache_dir / filename

    def cached_data(self, cache_path: Path) -> Optional[Union[List, Dict]]:
        """
        Load and return cached data if the cache file exists and is still valid.

        Validity is checked by ``cache_valid``, which returns ``True`` when
        the file is *older* than :attr:`cache_minutes`.  The logic is inverted
        here: ``is_still_valid = not cache_valid(...)`` so that ``True`` means
        "the file is fresh".

        When the file exists but contains malformed JSON or cannot be read, it
        is silently deleted and ``None`` is returned so that the caller
        proceeds with a live API request.

        :param cache_path: Full path to the cache file, typically obtained via
                           :meth:`cache_path`.
        :returns:          Deserialised JSON content (list or dict) on a valid
                           cache hit, or ``None`` on a cache miss, expiry, or
                           read error.
        """
        if not self.cache_dir:
            return None

        # cache_valid returns True when the file is *stale* (older than TTL).
        # Invert to get "is the cache still fresh?".
        is_still_valid = not cache_valid(
            self.module, str(cache_path), self.cache_minutes, True
        )

        if is_still_valid and cache_path.exists():
            try:
                with cache_path.open("r", encoding="utf-8") as f:
                    return json.load(f)
            except (json.JSONDecodeError, OSError):
                # Corrupted or unreadable cache file — remove and signal a miss
                try:
                    cache_path.unlink()
                except OSError:
                    pass

        return None

    def write_cache(self, cache_path: Path, data) -> None:
        """
        Serialise *data* as JSON and write it to *cache_path*.

        The file is written atomically in the sense that a complete
        ``json.dump`` is performed before closing; partial writes due to
        interruption are possible but rare for the typical small API payloads
        involved here.

        Has no effect when :attr:`cache_dir` is falsy.

        :param cache_path: Destination :class:`pathlib.Path`, typically
                           obtained via :meth:`cache_path`.
        :param data:       JSON-serialisable object (list or dict).
        """
        if not self.cache_dir:
            return

        try:
            with cache_path.open("w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except OSError as e:
            self.module.log(msg=f"Failed to write cache file: {e}")
