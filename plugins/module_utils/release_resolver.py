"""
release_resolver.py
===================

Provider-independent orchestration that turns a single release query into
everything an Ansible role needs to download and verify a release artefact:
the resolved version, the artefact download URL, the artefact filename and the
matching checksum (hash + algorithm + source).

The resolver talks only to a :class:`ReleaseBackend` (see ``release_backend``),
so the same matching/checksum logic serves GitHub, Forgejo/Gitea and — later —
GitLab without modification.  Because the *exact* artefact filename is known
after asset selection, checksum matching uses that filename as the lookup key
instead of reconstructed ``repo.*system.*arch`` fragments — the central
robustness improvement over the previous per-module heuristics.

Backwards compatibility
------------------------
For callers written against the original GitHub-only resolver, the legacy
``github=`` keyword is still accepted and is transparently wrapped in a
:class:`GitHubBackend`.  New callers should pass ``backend=`` instead.

Asset matching strategy (hybrid, see :meth:`ReleaseResolver._select_asset`)
---------------------------------------------------------------------------
* **Heuristic (default)** — synonym-aware substring matching of OS and CPU
  architecture (e.g. ``x86_64`` also matches ``amd64``), then a configurable
  archive extension preference.
* **Explicit override** — an ``asset`` template (``{version}``/``{tag}``/
  ``{system}``/``{arch}``) or an ``asset_regex`` pins the match.

Ambiguous matches fail with the candidate list rather than guessing.

Checksum strategy (see :meth:`ReleaseResolver._find_checksum`)
--------------------------------------------------------------
``per_artifact`` sidecar files, ``aggregate`` checksum files (GNU coreutils and
BSD formats, matched by exact artefact basename) and ``none`` (no checksum;
non-fatal) are all handled.

:author:  Bodo Schulz <bodo@boone-schulz.de>
:license: Apache-2.0
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from ansible_collections.bodsch.scm.plugins.module_utils.release_finder import ReleaseFinder
from packaging.version import InvalidVersion, Version

__metaclass__ = type


# Operating-system token synonyms keyed by the normalised (lowercase) value.
SYSTEM_SYNONYMS: Dict[str, List[str]] = {
    "linux": ["linux"],
    "darwin": ["darwin", "macos", "osx", "apple-darwin"],
    "windows": ["windows", "win"],
    "freebsd": ["freebsd"],
    "openbsd": ["openbsd"],
    "netbsd": ["netbsd"],
}

# CPU-architecture token synonyms keyed by the normalised (lowercase) value.
# Deliberately omits the bare token ``arm`` to avoid ``arm64`` matching an
# ``armv7`` request (and vice versa).
ARCH_SYNONYMS: Dict[str, List[str]] = {
    "x86_64": ["x86_64", "amd64"],
    "amd64": ["amd64", "x86_64"],
    "aarch64": ["aarch64", "arm64"],
    "arm64": ["arm64", "aarch64"],
    "armv7l": ["armv7", "armv7l", "armhf"],
    "armv7": ["armv7", "armv7l", "armhf"],
    "armv6l": ["armv6", "armv6l"],
    "armv6": ["armv6", "armv6l"],
    "i386": ["i386", "386", "i686"],
    "i686": ["i686", "i386", "386"],
    "ppc64le": ["ppc64le", "powerpc64le"],
    "ppc64": ["ppc64", "powerpc64"],
    "s390x": ["s390x"],
    "riscv64": ["riscv64"],
    "mips64": ["mips64"],
    "mips64le": ["mips64le"],
}

# Ordered archive-extension preference used to disambiguate matching artefacts.
DEFAULT_EXTENSIONS: List[str] = [".tar.gz", ".tgz", ".tar.xz", ".tar.bz2", ".zip"]

# Sidecar checksum filename suffixes tried (in order) for the per-artefact case.
_PER_ARTIFACT_SUFFIXES: List[str] = [
    ".sha256",
    ".sha512",
    ".sha384",
    ".sha256sum",
    ".sha512sum",
    ".sha1",
    ".md5",
    ".sum",
]

# Default keywords excluded when resolving ``version="latest"``.
DEFAULT_EXCLUDE_KEYWORDS: List[str] = ["beta", "rc", "preview", "alpha", "nightly"]

# Assets that are never download artefacts (signatures, checksums, SBOMs, ...).
_METADATA_RE = re.compile(
    r"("
    r"\.sha\d+(sum)?$|"
    r"\.sha\d+sums?$|"
    r"sha\d+sums?|"
    r"check[\s_-]?sums?|"
    r"\.md5(sum)?$|"
    r"\.sum$|"
    r"\.asc$|\.sig$|\.minisig$|\.pem$|\.pub$|"
    r"\.sbom|\.spdx|"
    r"source[\s_-]?code"
    r")",
    re.IGNORECASE,
)

# Aggregate checksum-file recognition (matched against the asset name).
_AGGREGATE_RE = re.compile(r"(sha\d+sums?|check[\s_-]?sums?)", re.IGNORECASE)

# GNU coreutils checksum line: "<hex>  [*]<filename>".
_GNU_RE = re.compile(r"^([0-9a-fA-F]{32,128})\s+[*]?(.+?)\s*$")

# BSD-style checksum line: "SHA256 (filename) = <hex>".
_BSD_RE = re.compile(
    r"^(?:SHA1|SHA224|SHA256|SHA384|SHA512|MD5)\s*\((.+)\)\s*=\s*([0-9a-fA-F]+)\s*$",
    re.IGNORECASE,
)

# Hash length (hex chars) -> checksum algorithm accepted by ansible get_url.
_HASH_LENGTH_ALGO: Dict[int, str] = {
    32: "md5",
    40: "sha1",
    56: "sha224",
    64: "sha256",
    96: "sha384",
    128: "sha512",
}


class ResolverError(Exception):
    """
    Raised when a release, artefact, or checksum cannot be resolved.

    Attributes
    ----------
    msg : str
        Human-readable error description.
    candidates : list of str
        Asset names considered (empty when not applicable).
    status : int
        HTTP-like status code for the Ansible module to return.
    """

    def __init__(
        self, msg: str, candidates: Optional[List[str]] = None, status: int = 500
    ) -> None:
        """
        Initialise the error.

        :param msg:        Human-readable error description.
        :param candidates: Optional list of asset names considered.
        :param status:     HTTP-like status code (default ``500``).
        """
        super().__init__(msg)
        self.msg = msg
        self.candidates = candidates or []
        self.status = status


@dataclass
class ResolvedRelease:
    """
    Result container for a successful release resolution.

    Attributes
    ----------
    version : str
        Resolved version without a leading ``"v"`` (e.g. ``"2.53.0"``).
    tag : str
        Git tag of the resolved release (e.g. ``"v2.53.0"``).
    file : str or None
        Filename of the selected artefact asset.
    download_url : str or None
        Direct download URL of the selected artefact asset.
    checksum : str or None
        Lowercase hex checksum, or ``None`` when no checksum source exists.
    checksum_algorithm : str or None
        Checksum algorithm name, or ``None``.
    checksum_url : str or None
        Download URL of the checksum source asset, or ``None``.
    checksum_source : str
        One of ``"per_artifact"``, ``"aggregate"`` or ``"none"``.
    assets : list of str
        Names of all assets attached to the resolved release.
    """

    version: str
    tag: str
    file: Optional[str] = None
    download_url: Optional[str] = None
    checksum: Optional[str] = None
    checksum_algorithm: Optional[str] = None
    checksum_url: Optional[str] = None
    checksum_source: str = "none"
    assets: List[str] = field(default_factory=list)

    @property
    def checksum_string(self) -> Optional[str]:
        """
        Return ``"<algorithm>:<hash>"`` for use in ``get_url``'s ``checksum``
        parameter, or ``None`` when no checksum is available.

        :returns: e.g. ``"sha256:e3b0c442..."`` or ``None``.
        """
        if self.checksum and self.checksum_algorithm:
            return f"{self.checksum_algorithm}:{self.checksum}"
        return None

    def to_dict(self) -> Dict[str, Any]:
        """
        Serialise the result to a plain dict suitable for ``exit_json``.

        :returns: Dict with all public fields plus ``checksum_string``.
        """
        return {
            "version": self.version,
            "tag": self.tag,
            "file": self.file,
            "download_url": self.download_url,
            "checksum": self.checksum,
            "checksum_algorithm": self.checksum_algorithm,
            "checksum_string": self.checksum_string,
            "checksum_url": self.checksum_url,
            "checksum_source": self.checksum_source,
            "assets": self.assets,
        }


class ReleaseResolver:
    """
    Resolve a release to a downloadable, verifiable artefact via a backend.

    Attributes
    ----------
    module : AnsibleModule
        Ansible module instance used for logging.
    backend : ReleaseBackend
        Provider backend supplying releases, assets and text fetches.
    system : str
        Lowercased target operating system (e.g. ``"linux"``).
    architecture : str
        Lowercased target CPU architecture (e.g. ``"x86_64"``).
    """

    def __init__(
        self,
        module: Any,
        backend: Any = None,
        system: str = "",
        architecture: str = "",
        asset: Optional[str] = None,
        asset_regex: Optional[str] = None,
        extensions: Optional[List[str]] = None,
        exclude_keywords: Optional[List[str]] = None,
        github: Any = None,
    ) -> None:
        """
        Initialise the resolver.

        :param module:           Ansible module instance (used for logging).
        :param backend:          A :class:`ReleaseBackend` implementation.
        :param system:           Target operating system (case-insensitive).
        :param architecture:     Target CPU architecture (case-insensitive).
        :param asset:            Optional explicit artefact filename template
                                 (``{version}``/``{tag}``/``{system}``/
                                 ``{arch}``).  Mutually exclusive with
                                 *asset_regex*.
        :param asset_regex:      Optional regex matched against asset names.
                                 Mutually exclusive with *asset*.
        :param extensions:       Ordered archive-extension preference.
                                 Defaults to :data:`DEFAULT_EXTENSIONS`.
        :param exclude_keywords: Keywords excluded when resolving ``"latest"``.
                                 Defaults to :data:`DEFAULT_EXCLUDE_KEYWORDS`.
        :param github:           Deprecated. A legacy :class:`GitHub` client;
                                 transparently wrapped in a
                                 :class:`GitHubBackend` when *backend* is not
                                 supplied.
        :raises ValueError:      When neither *backend* nor *github* is given.
        """
        self.module = module

        if backend is None and github is not None:
            # Backwards-compatible path for the original GitHub-only callers
            # (e.g. the github_release module). The legacy GitHub client is no
            # longer wrapped; instead a native GitHubBackend is reconstructed
            # from its owner/repository/token/cache settings, so existing
            # callers keep working while routing through the new transport.
            from ansible_collections.bodsch.scm.plugins.module_utils.github_backend import \
                GitHubBackend  # noqa: E501

            backend = GitHubBackend(
                module=module,
                owner=github.github_owner,
                repository=github.github_repository,
                token=getattr(github, "gh_auth_token", None),
                cache_minutes=getattr(
                    getattr(github, "gh_cache", None), "cache_minutes", 60
                ),
            )

        if backend is None:
            raise ValueError(
                "ReleaseResolver requires 'backend' (or the legacy 'github')."
            )

        self.backend = backend
        self.system = (system or "").lower()
        self.architecture = (architecture or "").lower()
        self._asset_template = asset
        self.asset_regex = asset_regex
        self.extensions = extensions or list(DEFAULT_EXTENSIONS)
        self.exclude_keywords = (
            exclude_keywords
            if exclude_keywords is not None
            else list(DEFAULT_EXCLUDE_KEYWORDS)
        )

    # ------------------------------------------------------------------------------------------
    # Public API

    def resolve(self, version: str) -> ResolvedRelease:
        """
        Resolve *version* into a fully populated :class:`ResolvedRelease`.

        :param version:        ``"latest"`` or a concrete version
                               (``"2.53.0"`` / ``"v2.53.0"``).
        :returns:              A populated :class:`ResolvedRelease`.
        :raises ResolverError: When the repository, release, or artefact cannot
                               be resolved (a missing checksum does not raise).
        """
        release = self._resolve_release(version)
        tag = release.get("tag_name") or ""
        resolved_version = (
            ReleaseFinder.extract_version_from_string(tag)
            or ReleaseFinder.extract_version_from_string(release.get("name", "") or "")
            or tag.lstrip("v")
        )

        status, assets, error = self.backend.get_assets(tag)
        if status != 200:
            raise ResolverError(
                f"Could not fetch assets for tag '{tag}': {error}", status=status
            )

        asset_names = [a.get("name", "") for a in assets]
        result = ResolvedRelease(version=resolved_version, tag=tag, assets=asset_names)

        artefact = self._select_asset(assets, resolved_version, tag)
        result.file = artefact.get("name")
        result.download_url = artefact.get("url")

        checksum_url, source = self._find_checksum(artefact, assets)
        result.checksum_source = source
        result.checksum_url = checksum_url

        if checksum_url:
            c_status, text, c_error = self.backend.get_text(checksum_url)
            if c_status == 200 and text:
                checksum, algo = self._extract_hash(text, artefact["name"], source)
                result.checksum = checksum
                result.checksum_algorithm = algo
            else:
                self.module.log(
                    msg=f"ReleaseResolver: checksum fetch failed "
                    f"({c_status}): {c_error}"
                )
                result.checksum_source = "none"
                result.checksum_url = None

        return result

    # ------------------------------------------------------------------------------------------
    # Private API - release selection

    def _resolve_release(self, version: str) -> Dict[str, Any]:
        """
        Select the release matching *version* from the backend's releases.

        :param version:        ``"latest"`` or a concrete version string.
        :returns:              The matching release dict (with ``tag_name``).
        :raises ResolverError: When no releases exist or none match *version*.
        """
        repo = f"{self.backend.owner}/{self.backend.repository}"
        status, releases, error = self.backend.get_releases()

        if status != 200:
            raise ResolverError(
                f"Backend request failed for {repo}: {error}", status=status
            )
        if not releases:
            raise ResolverError(f"No releases found for {repo}.", status=404)

        if str(version).strip().lower() == "latest":
            latest = self._latest(releases)
            if not latest:
                raise ResolverError(
                    f"No non-excluded release found for {repo}.", status=404
                )
            return latest

        match = self._match_concrete(releases, version)
        if not match:
            raise ResolverError(
                f"No release matching version '{version}' found for {repo}.",
                status=404,
            )
        return match

    def _latest(self, releases: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """
        Return the highest non-excluded SemVer release via :class:`ReleaseFinder`.

        :param releases: List of normalised release dicts.
        :returns:        The winning release dict, or ``None``.
        """
        finder = ReleaseFinder(module=self.module, releases=releases)
        finder.set_exclude_keywords(keywords=self.exclude_keywords)
        return finder.find_latest(mode="version")

    @staticmethod
    def _match_concrete(
        releases: List[Dict[str, Any]], version: str
    ) -> Optional[Dict[str, Any]]:
        """
        Find the release matching a concrete *version* robustly.

        Comparison order per field (``tag_name`` then ``name``): exact match
        after stripping ``"v"``, then embedded-version extraction compared as
        plain string and as SemVer.

        :param releases: List of release dicts.
        :param version:  Concrete version string (with or without ``"v"``).
        :returns:        The matching release dict, or ``None``.
        """
        target_plain = str(version).lstrip("v")
        try:
            target_ver: Optional[Version] = Version(target_plain)
        except InvalidVersion:
            target_ver = None

        for release in releases:
            for field_name in ("tag_name", "name"):
                raw = release.get(field_name) or ""
                if raw.lstrip("v") == target_plain:
                    return release

                extracted = ReleaseFinder.extract_version_from_string(raw)
                if not extracted:
                    continue
                if extracted == target_plain:
                    return release
                if target_ver is not None:
                    try:
                        if Version(extracted) == target_ver:
                            return release
                    except InvalidVersion:
                        pass
        return None

    # ------------------------------------------------------------------------------------------
    # Private API - artefact selection

    def _select_asset(
        self, assets: List[Dict[str, Any]], version: str, tag: str
    ) -> Dict[str, Any]:
        """
        Select the artefact asset using the hybrid strategy.

        :param assets:         List of asset dicts (``name``/``url``/``size``).
        :param version:        Resolved version (for template rendering).
        :param tag:            Resolved tag (for template rendering).
        :returns:              The selected artefact asset dict.
        :raises ResolverError: On zero or ambiguous matches.
        """
        all_names = [a.get("name", "") for a in assets]

        if self.asset_regex:
            try:
                rx = re.compile(self.asset_regex)
            except re.error as exc:
                raise ResolverError(f"Invalid asset_regex: {exc}", status=400)
            candidates = [a for a in assets if rx.search(a.get("name", ""))]
        elif self._asset_template:
            rendered = self._render_asset_template(version, tag)
            candidates = [a for a in assets if a.get("name") == rendered]
            if not candidates:
                candidates = [a for a in assets if a.get("name", "").endswith(rendered)]
        else:
            candidates = self._heuristic_candidates(assets)

        candidates = [
            a for a in candidates if not self._is_metadata_asset(a.get("name", ""))
        ]

        if not candidates:
            raise ResolverError(
                "No artefact asset matched the requested system/architecture.",
                candidates=all_names,
            )

        preferred = self._prefer_by_extension(candidates)
        if len(preferred) > 1:
            raise ResolverError(
                "Artefact match is ambiguous; refine with 'asset' or "
                "'asset_regex', or set 'extensions'.",
                candidates=[a.get("name", "") for a in preferred],
            )

        return preferred[0]

    def _render_asset_template(self, version: str, tag: str) -> str:
        """
        Render the explicit ``asset`` template.

        Placeholders: ``{version}`` (without ``v``), ``{tag}`` (raw tag),
        ``{system}`` (lowercased) and ``{arch}`` (raw architecture).

        :param version:        Resolved version string.
        :param tag:            Resolved tag string.
        :returns:              The rendered filename.
        :raises ResolverError: On an unknown placeholder.
        """
        try:
            return self._asset_template.format(
                version=version,
                tag=tag,
                system=self.system,
                arch=self.architecture,
            )
        except (KeyError, IndexError) as exc:
            raise ResolverError(
                f"Invalid placeholder in asset template: {exc}", status=400
            )

    def _heuristic_candidates(
        self, assets: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Filter assets by system and architecture synonym tokens.

        :param assets: List of asset dicts.
        :returns:      Matching asset dicts (possibly empty).
        """
        sys_tokens = SYSTEM_SYNONYMS.get(
            self.system, [self.system] if self.system else []
        )
        arch_tokens = ARCH_SYNONYMS.get(
            self.architecture, [self.architecture] if self.architecture else []
        )

        out: List[Dict[str, Any]] = []
        for asset in assets:
            name = asset.get("name", "").lower()
            if sys_tokens and not any(tok in name for tok in sys_tokens):
                continue
            if arch_tokens and not any(tok in name for tok in arch_tokens):
                continue
            out.append(asset)
        return out

    def _prefer_by_extension(
        self, candidates: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Reduce *candidates* to those sharing the most-preferred extension.

        :param candidates: List of candidate asset dicts.
        :returns:          The reduced (or unchanged) candidate list.
        """
        for ext in self.extensions:
            matched = [
                a for a in candidates if a.get("name", "").lower().endswith(ext.lower())
            ]
            if matched:
                return matched
        return candidates

    @staticmethod
    def _is_metadata_asset(name: str) -> bool:
        """
        Return ``True`` when *name* denotes a non-artefact metadata asset.

        :param name: Asset filename.
        :returns:    ``True`` for metadata assets, ``False`` otherwise.
        """
        return bool(_METADATA_RE.search(name or ""))

    # ------------------------------------------------------------------------------------------
    # Private API - checksum resolution

    def _find_checksum(
        self, artefact: Dict[str, Any], assets: List[Dict[str, Any]]
    ) -> Tuple[Optional[str], str]:
        """
        Locate the checksum source for *artefact* among *assets*.

        Per-artefact sidecars take precedence over aggregate files; aggregates
        are ranked sha256 -> sha512 -> generic.

        :param artefact: The selected artefact asset dict.
        :param assets:   All asset dicts of the release.
        :returns:        ``(checksum_url, source)`` with *source* in
                         ``per_artifact`` / ``aggregate`` / ``none``.
        """
        artefact_name = artefact.get("name", "")
        by_name = {a.get("name", ""): a for a in assets}

        for suffix in _PER_ARTIFACT_SUFFIXES:
            sidecar = by_name.get(artefact_name + suffix)
            if sidecar:
                return sidecar.get("url"), "per_artifact"

        aggregates = [
            a
            for a in assets
            if _AGGREGATE_RE.search(a.get("name", ""))
            and not a.get("name", "").lower().endswith((".asc", ".sig", ".pem"))
        ]
        if aggregates:
            aggregates.sort(key=self._aggregate_rank)
            return aggregates[0].get("url"), "aggregate"

        return None, "none"

    @staticmethod
    def _aggregate_rank(asset: Dict[str, Any]) -> int:
        """
        Deterministic sort key for aggregate checksum files
        (sha256 < sha512 < other).

        :param asset: Asset dict.
        :returns:     ``0`` / ``1`` / ``2``.
        """
        name = asset.get("name", "").lower()
        if "sha256" in name:
            return 0
        if "sha512" in name:
            return 1
        return 2

    def _extract_hash(
        self, text: str, artefact_name: str, source: str
    ) -> Tuple[Optional[str], Optional[str]]:
        """
        Extract the artefact hash from a checksum file body.

        :param text:          Raw checksum file body.
        :param artefact_name: Filename of the artefact to look up.
        :param source:        ``"per_artifact"`` or ``"aggregate"``.
        :returns:             ``(hash, algorithm)`` or ``(None, None)``.
        """
        entries = self._parse_checksum_text(text)

        if source == "per_artifact":
            if entries:
                checksum, filename = entries[0]
                return checksum, self._algorithm_for(checksum, filename)
            token = text.strip().split()[0] if text and text.strip() else None
            if token and re.fullmatch(r"[0-9a-fA-F]{32,128}", token):
                return token.lower(), self._algorithm_for(token, artefact_name)
            return None, None

        for checksum, filename in entries:
            if filename == artefact_name or filename.split("/")[-1] == artefact_name:
                return checksum, self._algorithm_for(checksum, filename)
        return None, None

    @staticmethod
    def _parse_checksum_text(text: str) -> List[Tuple[str, str]]:
        """
        Parse a checksum file body into ``(hash, basename)`` tuples.

        Supports GNU coreutils and BSD line formats; blank lines and ``#``
        comments are ignored.

        :param text: Raw checksum file body.
        :returns:    List of ``(lowercase_hash, basename)`` tuples.
        """
        out: List[Tuple[str, str]] = []
        for line in text.splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue

            bsd = _BSD_RE.match(line)
            if bsd:
                filename, checksum = bsd.group(1).strip(), bsd.group(2)
                out.append((checksum.lower(), filename.split("/")[-1]))
                continue

            gnu = _GNU_RE.match(line)
            if gnu:
                checksum, filename = gnu.group(1), gnu.group(2).strip()
                out.append((checksum.lower(), filename.split("/")[-1]))
        return out

    @staticmethod
    def _algorithm_for(checksum: str, filename: str) -> Optional[str]:
        """
        Infer the checksum algorithm from hash length, with a filename fallback.

        :param checksum: Hex hash string.
        :param filename: Associated filename (hint when length is ambiguous).
        :returns:        Algorithm name (``"sha256"`` ...) or ``None``.
        """
        algo = _HASH_LENGTH_ALGO.get(len(checksum or ""))
        if algo:
            return algo

        low = (filename or "").lower()
        for candidate in ("sha512", "sha384", "sha256", "sha224", "sha1", "md5"):
            if candidate in low:
                return candidate
        return None
