"""
release_finder.py
=================

Utility module for identifying the most relevant release from a list of GitHub
release metadata dicts.

Supports descriptive release names such as ``"GLAuth v2.3.0"`` or
``"Grafana 11.6.3 / 2025-06-17"`` by extracting embedded version strings via
regex before falling back to direct ``packaging.version`` parsing.

Typical usage
-------------
::

    from release_finder import ReleaseFinder

    finder = ReleaseFinder(module=ansible_module, releases=release_list)
    finder.set_exclude_keywords(["beta", "rc", "preview"])
    latest = finder.find_latest(mode="version")

Release dict shape expected by this module
------------------------------------------
::

    {
        "name":         str,  # human-readable release title (may be descriptive)
        "tag_name":     str,  # git tag (e.g. "v2.3.0")
        "published_at": str,  # ISO-8601 timestamp (e.g. "2025-06-17T21:41:45Z")
        "url":          str,  # HTML URL of the release page
    }

:license: Apache-2.0
"""

import re
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from dateutil import parser as date_parser
from packaging.version import InvalidVersion, Version
from packaging.version import parse as parse_version

# Compiled regex that recognises semver-like version strings embedded inside
# arbitrary text.  The leading "v" prefix is optional and not captured.
#
# Matches examples:
#   "GLAuth v2.3.0"               → group(1) = "2.3.0"
#   "Release 10.4.19+security-01" → group(1) = "10.4.19+security-01"
#   "v12.0.2"                     → group(1) = "12.0.2"
_VERSION_PATTERN = re.compile(r"\bv?(\d+\.\d+(?:\.\d+)?(?:[+\-][^\s,)]*)?)\b")


class ReleaseFinder:
    """
    Identify the most relevant release entry from a list of GitHub releases.

    Handles repositories where release ``name`` fields contain descriptive
    prefixes or suffixes (e.g. ``"GLAuth v2.3.0"``, ``"Grafana 11.6.3 /
    2025-06-17"``) by extracting embedded version strings before comparison.

    Three selection modes are supported (see :meth:`find_latest`):

    * ``"published"`` — highest combination of publication date and SemVer
      (default; tolerates back-ported patch releases published after a newer
      major).
    * ``"version"``   — strictly highest SemVer, ignoring publication date.
    * ``"security"``  — highest SemVer among security releases only
      (identified by a ``+security`` suffix in ``tag_name`` or ``name``).

    Attributes
    ----------
    module : AnsibleModule
        Ansible module instance used for logging.
    releases : list of dict
        Raw release data as provided at construction time.
    exclude_patterns : list of re.Pattern
        Compiled regex patterns used to filter out unwanted releases.
        Populated by :meth:`set_exclude_keywords`.
    """

    def __init__(self, module: any, releases: List[Dict[str, Any]]) -> None:
        """
        Initialise the finder with a list of release metadata dicts.

        Example input::

            [
                {
                    "name": "12.0.2",
                    "tag_name": "v12.0.2",
                    "published_at": "2025-06-17T21:41:45Z",
                    "url": "",
                },
                {
                    "name": "GLAuth v2.3.0",
                    "tag_name": "v2.3.0",
                    "published_at": "2025-05-01T10:00:00Z",
                    "url": "",
                },
            ]

        :param module:   Ansible module instance (used for ``module.log``).
        :param releases: List of release dicts.  Each dict must contain at
                         least ``"tag_name"`` and ``"published_at"`` keys.
                         ``"name"`` is optional but improves version detection
                         for descriptive release titles.
        """
        self.module = module
        self.releases = releases
        self.exclude_patterns: List[re.Pattern] = []

    # ------------------------------------------------------------------------------------------
    # Public API

    def find_latest(self, mode: str = "published") -> Optional[Dict[str, Any]]:
        """
        Return the most relevant release according to the selected *mode*.

        Releases that match any configured exclude pattern (see
        :meth:`set_exclude_keywords`) are removed before evaluation.

        Sorting keys per mode:

        * ``"published"``  — ``(published_at, semver)``; a recently published
          older patch release ranks below a newer version published earlier.
        * ``"version"``    — ``semver`` only; publication date is ignored.
        * ``"security"``   — ``semver`` within the subset of security releases
          (entries whose ``tag_name`` or ``name`` contains ``+security``).

        When the winning release has an empty ``"name"`` field, ``"tag_name"``
        is used as a fallback to guarantee a non-empty name is always returned.

        :param mode: Selection strategy — one of ``"published"`` (default),
                     ``"version"``, or ``"security"``.
        :returns:    The winning release dict, or ``None`` if no valid
                     candidates remain after filtering.
        """
        self.module.log(msg=f"ReleaseFinder::find_latest(mode={mode})")

        candidates = (
            self._get_candidate(r) for r in self.releases if not self._is_excluded(r)
        )
        candidates = filter(None, candidates)

        if mode == "security":
            candidates = filter(lambda x: self._is_security_release(x[2]), candidates)

        try:
            if mode in ("version", "security"):
                _, _, latest = max(candidates, key=lambda x: x[1])
            else:
                _, _, latest = max(candidates, key=lambda x: (x[0], x[1]))

            # Guarantee a non-empty name field
            if not latest.get("name"):
                latest["name"] = latest.get("tag_name")

            return latest
        except ValueError:
            return None

    def set_exclude_keywords(self, keywords: List[str]) -> None:
        """
        Configure a case-insensitive keyword filter for release exclusion.

        Any release whose ``name`` or ``tag_name`` matches at least one of the
        provided *keywords* is excluded from :meth:`find_latest` results.
        Calling this method again replaces any previously configured filter.
        Passing an empty list clears all filters.

        Internally a single compiled regex of the form
        ``.*(<kw1>|<kw2>|...).*`` is stored.

        :param keywords: List of substrings to exclude, e.g.
                         ``["beta", "rc", "preview", "nightly"]``.
                         Case-insensitive matching is applied automatically.
        """
        if not keywords:
            self.exclude_patterns = []
            return

        pattern = "|".join(map(re.escape, keywords))
        regex = re.compile(rf".*({pattern}).*", re.IGNORECASE)
        self.exclude_patterns = [regex]

    # ------------------------------------------------------------------------------------------
    # Private API

    @staticmethod
    def extract_version_from_string(text: str) -> Optional[str]:
        """
        Extract the first semver-like version string embedded in *text*.

        Uses :data:`_VERSION_PATTERN` to locate a version token.  The
        optional leading ``"v"`` is stripped from the returned value.

        Examples::

            "GLAuth v2.3.0"               → "2.3.0"
            "Release 10.4.19+security-01" → "10.4.19+security-01"
            "v12.0.2"                     → "12.0.2"
            "no version here"             → None

        This method is intentionally public (``@staticmethod``) so that it can
        be reused by other modules (e.g. ``github_releases.py``) without
        instantiating :class:`ReleaseFinder`.

        :param text: Arbitrary string that may contain a version token.
        :returns:    Extracted version string without leading ``"v"``, or
                     ``None`` if no version pattern was found.
        """
        match = _VERSION_PATTERN.search(text)
        return match.group(1) if match else None

    def _parse_date_iso(self, release: Dict[str, Any]) -> Optional[datetime]:
        """
        Parse the ISO-8601 timestamp from the ``"published_at"`` field.

        Uses ``dateutil.parser.parse`` for lenient parsing of various ISO
        timestamp variants including timezone offsets.

        :param release: Release dict containing an optional ``"published_at"``
                        key.
        :returns:       Timezone-aware :class:`datetime` on success, or
                        ``None`` when the field is absent or unparsable.
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
        Fallback date parser that extracts a ``YYYY-MM-DD`` date from the
        ``"name"`` field.

        Matches the pattern ``/ YYYY-MM-DD`` (slash-separated date annotation)
        as used by some projects, e.g.::

            "Release v2.0.0 / 2025-05-27"

        :param release: Release dict whose ``"name"`` may contain an embedded
                        date.
        :returns:       Naive :class:`datetime` for the extracted date, or
                        ``None`` if no date annotation was found.
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
        Derive a :class:`packaging.version.Version` from a release dict.

        The following strategies are tried in order, stopping at the first
        success:

        1. Direct parse of ``tag_name`` after stripping a leading ``"v"``
           (e.g. ``"v2.3.0"`` → ``Version("2.3.0")``).
        2. Regex extraction from ``tag_name`` for descriptive tags
           (e.g. ``"project-v2.3.0"`` → ``"2.3.0"``).
        3. Direct parse of ``name`` after stripping a leading ``"v"``.
        4. Regex extraction from ``name``
           (e.g. ``"GLAuth v2.3.0"`` → ``"2.3.0"``).

        :param release: Release dict.
        :returns:       Parsed :class:`Version`, or ``Version("0.0.0")`` when
                        no valid version string is found in either field.
        """
        for field in ("tag_name", "name"):
            raw = release.get(field, "") or ""

            # Strategy 1 / 3: direct parse after stripping optional "v" prefix
            try:
                return parse_version(raw.lstrip("v"))
            except InvalidVersion:
                pass

            # Strategy 2 / 4: regex extraction from descriptive string
            extracted = self.extract_version_from_string(raw)
            if extracted:
                try:
                    return parse_version(extracted)
                except InvalidVersion:
                    pass

        return parse_version("0.0.0")

    def _get_candidate(
        self, release: Dict[str, Any]
    ) -> Optional[Tuple[datetime, Version, Dict[str, Any]]]:
        """
        Build a sortable candidate tuple for a single release.

        The tuple ``(datetime, Version, release_dict)`` is used as the sort
        key in :meth:`find_latest`.  Returns ``None`` for releases where no
        publication date can be determined (neither ISO timestamp nor
        name-embedded date), as these cannot be meaningfully sorted.

        :param release: Release dict.
        :returns:       ``(published_at, semver, release)`` tuple, or ``None``
                        when no date is available.
        """
        dt = self._parse_date_iso(release) or self._parse_date_from_name(release)
        if dt is None:
            return None

        sem = self._parse_semver(release)
        self.module.log(msg=f"dt={dt}, sem={sem}, release={release}")

        return dt, sem, release

    def _is_security_release(self, release: Dict[str, Any]) -> bool:
        """
        Return ``True`` when the release is identified as a security release.

        A release is considered a security release when either ``tag_name`` or
        ``name`` contains the literal substring ``"+security"``.

        :param release: Release dict.
        :returns:       ``True`` if the release is a security release,
                        ``False`` otherwise.
        """
        tag = release.get("tag_name", "")
        name = release.get("name", "")
        return "+security" in tag or "+security" in name

    def _is_excluded(self, release: Dict[str, Any]) -> bool:
        """
        Return ``True`` when the release should be excluded from results.

        Compares ``name`` and ``tag_name`` against every pattern in
        :attr:`exclude_patterns`.  A single match on either field is
        sufficient to exclude the release.

        :param release: Release dict.
        :returns:       ``True`` if the release matches any exclude pattern,
                        ``False`` otherwise (including when no patterns are
                        configured).
        """
        name = release.get("name", "") or ""
        tag = release.get("tag_name", "") or ""

        for pattern in self.exclude_patterns:
            if pattern.search(name) or pattern.search(tag):
                return True

        return False
