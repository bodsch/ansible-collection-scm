import re
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from dateutil import parser as date_parser
from packaging.version import InvalidVersion, Version
from packaging.version import parse as parse_version


class ReleaseFinder:
    """
    To find the latest release entry from a list of releases.
    """

    def __init__(self, module: any, releases: List[Dict[str, Any]]) -> None:
        """
        Initialises the ReleaseFinder with raw release data.

        releases:  [
            {'name': '12.0.2', 'tag_name': 'v12.0.2', 'published_at': '2025-06-17T21:41:45Z', 'url': ''},
            {'name': '11.6.3', 'tag_name': 'v11.6.3', 'published_at': '2025-06-17T21:58:59Z', 'url': ''},
            {'name': '11.5.6', 'tag_name': 'v11.5.6', 'published_at': '2025-06-17T22:00:40Z', 'url': ''},
            {'name': '11.4.6', 'tag_name': 'v11.4.6', 'published_at': '2025-06-17T20:54:31Z', 'url': ''},
            {'name': '11.3.8', 'tag_name': 'v11.3.8', 'published_at': '2025-06-17T19:56:35Z', 'url': ''},
            {'name': '10.4.19+security-01', 'tag_name': 'v10.4.19+security-01', 'published_at': '2025-06-12T14:29:40Z', 'url': ''},
            {'name': '12.0.1+security-01', 'tag_name': 'v12.0.1+security-01', 'published_at': '2025-06-13T04:15:18Z', 'url': ''},
            {'name': '11.6.2+security-01', 'tag_name': 'v11.6.2+security-01', 'published_at': '2025-06-13T04:12:24Z', 'url': ''},
            {'name': '11.5.5+security-01', 'tag_name': 'v11.5.5+security-01', 'published_at': '2025-06-13T04:11:29Z', 'url': ''},
            {'name': '11.4.5+security-01', 'tag_name': 'v11.4.5+security-01', 'published_at': '2025-06-13T04:12:48Z', 'url': ''}
        ]

        :param releases:  List of dictionaries with keys “tag_name”, “published_at”, “name”, etc.
        """
        self.module = module
        self.releases = releases
        self.exclude_patterns: List[re.Pattern] = []

    # ------------------------------------------------------------------------------------------
    # public API
    def find_latest(self, mode: str = "published") -> Optional[Dict[str, Any]]:
        """ """
        self.module.log(msg=f"ReleaseFinder::find_latest(mode={mode})")

        # candidates = list(filter(None, (
        #     self._get_candidate(r)
        #     for r in self.releases
        #     if not self._is_excluded(r)
        # )))
        # # self.module.log(msg=f"Remaining candidates: {len(candidates)}")
        # # self.module.log(msg=f"          candidates: {candidates}")

        candidates = (
            self._get_candidate(r)
            for r in self.releases
            if not self._is_excluded(r)  # << Ausschlussfilter vorab
        )

        candidates = filter(None, candidates)

        if mode == "security":
            candidates = filter(lambda x: self._is_security_release(x[2]), candidates)

        try:
            if mode in ("version", "security"):
                _, _, latest = max(candidates, key=lambda x: x[1])
            else:
                _, _, latest = max(candidates, key=lambda x: (x[0], x[1]))

            _name = latest.get("name", None)
            _tag_name = latest.get("tag_name", None)
            if not _name or len(_name) == 0:
                latest["name"] = _tag_name

            return latest
        except ValueError:
            return None

    def set_exclude_keywords(self, keywords: List[str]) -> None:
        """
        Sets a regex pattern to exclude releases based on keywords found in name or tag_name.

        :param keywords: List of substrings like ['beta', 'rc', 'preview']
        """
        # self.module.log(msg=f"ReleaseFinder::set_exclude_keywords(keywords={keywords})")

        if not keywords:
            self.exclude_patterns = []
            return

        pattern = "|".join(map(re.escape, keywords))
        regex = re.compile(rf".*({pattern}).*", re.IGNORECASE)
        self.exclude_patterns = [regex]

        # self.module.log(msg=f"Exclude pattern set: {regex.pattern}")

    # ------------------------------------------------------------------------------------------
    # private API

    def _parse_date_iso(self, release: Dict[str, Any]) -> Optional[datetime]:
        """
        Attempts to parse the ISO date in the “published_at” field.
        Returns None if the value is missing or invalid.
        """
        raw = release.get("published_at")
        if not raw:
            return None
        try:
            return date_parser.parse(raw)
        except (ValueError, TypeError):
            return None

    def _parse_date_from_name(self, release: Dict[str, Any]) -> Optional[datetime]:
        """
        Fallback: Extract date from the “name” field in the format YYYY-MM-DD.
        Example: 'Release v2.0.0 / 2025-05-27'
        """
        name = release.get("name", "")
        match = re.search(r"/\s*(\d{4}-\d{2}-\d{2})", name)
        if not match:
            return None
        try:
            return datetime.fromisoformat(match.group(1))
        except ValueError:
            return None

    def _parse_semver(self, release: Dict[str, Any]) -> Version:
        """
        Parses the semantic version string “tag_name”.
        Returns version(“0.0.0”) if the tag is invalid.
        """
        tag = release.get("tag_name", "")
        try:
            return parse_version(tag)
        except InvalidVersion:
            return parse_version("0.0.0")

    def _get_candidate(
        self, release: Dict[str, Any]
    ) -> Optional[Tuple[datetime, Version, Dict[str, Any]]]:
        """
        Builds a tuple (Date, SemVer, ReleaseDict) for sorting.
        Returns None if no date was found.
        """
        self.module.log(msg=f"ReleaseFinder::_get_candidate({release}")

        dt = self._parse_date_iso(release) or self._parse_date_from_name(release)

        if dt is None:
            return None

        sem = self._parse_semver(release)

        self.module.log(msg=f"dt={dt}, sem={sem}, release={release}")

        return dt, sem, release

    def _find_latest_by_version(self) -> Optional[Dict[str, Any]]:
        """
        Finds the release with the highest semantic version.
        """
        candidates = filter(None, (self._get_candidate(r) for r in self.releases))

        try:
            _, version, latest = max(candidates, key=lambda x: x[1])
            return latest
        except ValueError:
            return None

    def _is_security_release(self, release: Dict[str, Any]) -> bool:
        """
        Returns True if the release appears to be a security release.
        """
        tag = release.get("tag_name", "")
        name = release.get("name", "")
        return "+security" in tag or "+security" in name

    def _is_excluded(self, release: Dict[str, Any]) -> bool:
        """
        Returns True if the release should be excluded based on configured regex patterns.
        """
        # self.module.log(msg=f"ReleaseFinder::_is_excluded(release={release})")

        name = release.get("name", "") or ""
        tag = release.get("tag_name", "") or ""

        for pattern in self.exclude_patterns:
            if pattern.search(name) or pattern.search(tag):
                # self.module.log(msg=f"Excluded by pattern: {pattern.pattern} -> {name} / {tag}")
                return True

        return False
