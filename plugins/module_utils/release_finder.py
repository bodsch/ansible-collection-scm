
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime
from dateutil import parser as date_parser
from packaging.version import Version, InvalidVersion, parse as parse_version
import re


class ReleaseFinder:
    """
    To find the latest release entry from a list of releases.
    """
    def __init__(self, releases: List[Dict[str, Any]]) -> None:
        """
        Initialises the ReleaseFinder with raw release data.

        :param releases:  List of dictionaries with keys “tag_name”, “published_at”, “name”, etc.
        """
        self.releases = releases

    def _parse_date_iso(self, release: Dict[str, Any]) -> Optional[datetime]:
        """
        Attempts to parse the ISO date in the “published_at” field.
        Returns None if the value is missing or invalid.
        """
        raw = release.get('published_at')
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
        name = release.get('name', '')
        match = re.search(r'/\s*(\d{4}-\d{2}-\d{2})', name)
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
        tag = release.get('tag_name', '')
        try:
            return parse_version(tag)
        except InvalidVersion:
            return parse_version("0.0.0")

    def _get_candidate(self, release: Dict[str, Any]) -> Optional[Tuple[datetime, Version, Dict[str, Any]]]:
        """
        Builds a tuple (Date, SemVer, ReleaseDict) for sorting.
        Returns None if no date was found.
        """
        dt = self._parse_date_iso(release) or self._parse_date_from_name(release)
        if dt is None:
            return None
        sem = self._parse_semver(release)
        return dt, sem, release

    def find_latest(self) -> Optional[Dict[str, Any]]:
        """
        Finds the release with the latest date or the highest SemVer with the same date.

        :return: The release dictionary of the latest entry or None if there is no valid release.
        """
        candidates = filter(None, (self._get_candidate(r) for r in self.releases))
        try:
            _, _, latest = max(candidates, key=lambda x: (x[0], x[1]))
            return latest
        except ValueError:
            return None
