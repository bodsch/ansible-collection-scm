# TODO — GitLab release backend

Status: **deferred** (future-proofing, no current consumer).
Priority: low. Pick up only when a concrete GitLab release source appears
(gitlab.com project or a self-hosted GitLab instance we actually pull from).

This document captures the design so the work can start cold without
re-researching the GitLab API.

---

## 0. Prerequisite

GitLab support depends on the shared multi-backend refactor being in place
first:

- `ReleaseBackend` protocol (the 3-method contract below)
- `BaseHTTPBackend` (shared transport: retries, pagination, rate-limit
  detection, on-disk cache — extracted from `GitHub._get_request`)
- `GitHubBackend` + `ForgejoBackend` as the first two implementations
- generic `scm_release` module dispatching on `provider`
- `github_release` kept as a thin, backwards-compatible shim

Do **not** implement GitLab before that scaffold exists; otherwise the leaky
GitLab specifics leak into the resolver instead of staying behind the backend.

---

## 1. Contract the backend must satisfy

The resolver only ever calls this surface. A `GitLabBackend` must provide
exactly it, normalising GitLab's response shapes to ours.

```python
owner: str           # GitLab namespace / group path
repository: str      # project name

# normalise to [{"name": str, "tag_name": str, "published_at": str, "url": str}]
def get_releases(self) -> Tuple[int, List[Dict], Optional[str]]: ...

# normalise to [{"name": str, "url": str, "size": Optional[int]}]
def get_assets(self, tag: str) -> Tuple[int, List[Dict], Optional[str]]: ...

# raw text body of a download URL (e.g. a checksum file)
def get_text(self, url: str) -> Tuple[int, Optional[str], Optional[str]]: ...
```

The resolver already tolerates `size = None`, so missing sizes are fine.

---

## 2. API specifics

- **Base path:** `/api/v4`. Self-hosted instances need a configurable
  `host` / `api_url` (same as Forgejo).
- **Project identifier:** numeric ID **or** URL-encoded full path, e.g.
  `group/subgroup/project` -> `group%2Fsubgroup%2Fproject`. The backend must
  URL-encode `owner/repository` when no numeric ID is given.
- **Auth header:** `PRIVATE-TOKEN: <token>` (also accepts
  `Authorization: Bearer <token>` and `JOB-TOKEN`/CI_JOB_TOKEN in CI). This
  differs from GitHub/Forgejo, which use `Authorization: token <token>` — so
  the auth-header strategy must be a per-backend hook on `BaseHTTPBackend`.
- **Pagination:** GitLab uses its own pagination (`Link` headers plus
  `X-Total-Pages` / `X-Next-Page`). Verify `BaseHTTPBackend`'s `Link`-header
  following works unchanged; if not, add a GitLab pagination hook.

### Endpoints

- Releases list: `GET /projects/:id/releases`
  (each release embeds `assets.links` and `assets.sources`).
- Single release / assets: the embedded `assets` object is usually enough;
  `GET /projects/:id/releases/:tag_name/assets/links` exists if a dedicated
  call is preferred.

---

## 3. Normalisation mapping

### Releases

GitLab release object -> our shape:

| ours           | GitLab field                                  |
|----------------|-----------------------------------------------|
| `name`         | `name`                                        |
| `tag_name`     | `tag_name`                                    |
| `published_at` | `released_at` (fallback `created_at`)         |
| `url`          | `_links.self` (or construct the release page) |

### Assets — the important divergence

GitLab release "assets" are **links, not uploaded files**. Each entry in
`assets.links[]` looks like:

```json
{
  "id": 2,
  "name": "hellodarwin-amd64",
  "url": "https://.../-/jobs/688/artifacts/raw/bin/hello-darwin-amd64",
  "direct_asset_url": "https://.../-/releases/v1.7.0/downloads/bin/hellodarwin-amd64",
  "link_type": "other"   // other | runbook | image | package
}
```

Mapping rule:

- `name`  <- `link.name`
- `url`   <- `link.direct_asset_url` **if present**, else `link.url`
  (direct_asset_url is the stable, permanent download path)
- `size`  <- `None` (not provided by the links API)

**Filter out** `assets.sources[]` entirely — these are the auto-generated
source archives (`zip`, `tar.gz`, `tar.bz2`, `tar`), the GitLab equivalent of
GitHub/Forgejo "Source code" archives. They are never the artefact we want.

---

## 4. Known gotchas / risks (why this is the leaky backend)

1. **Links can point anywhere.** A link's `url` may target a CI artefact, an
   external host, or the Package/Generic Package Registry — not necessarily a
   direct binary. Resolution may yield a URL that is not a plain file download.
2. **No size.** `get_assets` returns `size=None`; acceptable, but means no
   size-based sanity checks are possible.
3. **Weak checksum story.** Checksums are only available if the project
   published them as an explicit asset link. Aggregate `sha256sums.txt` /
   per-artefact sidecars are far less common than on GitHub/Forgejo. Expect
   `checksum_source: none` frequently. The resolver already handles this
   gracefully (non-fatal) — but document the expectation for users.
4. **Source archives** must be excluded (see §3).
5. **link_type hints.** `link_type == "package"` / `"image"` may indicate a
   registry artefact rather than a downloadable binary — consider letting the
   resolver/user filter on `link_type` later (optional refinement).

---

## 5. New / changed module options (for `scm_release`)

- `provider: gitlab` dispatches to `GitLabBackend`.
- `host` / `api_url`: required for self-hosted; defaults to
  `https://gitlab.com` for the SaaS case.
- `project_id` (optional): allow passing a numeric ID directly to skip path
  encoding for projects in nested subgroups.
- Token env convention: document `GITLAB_TOKEN` (vs `GH_TOKEN` /
  `FORGEJO_TOKEN`); the module param stays generic (`password`/`token`).

No resolver changes expected — that is the whole point of the abstraction.

---

## 6. Tests to add (mirror the existing resolver scenarios)

Add a `GitLabBackend` fixture returning realistic GitLab payloads and re-run
the resolver scenarios, plus GitLab-specific ones:

- [ ] release normalisation (`released_at` -> `published_at`, fallback to
      `created_at`)
- [ ] asset link mapping prefers `direct_asset_url` over `url`
- [ ] `assets.sources` archives are filtered out and never selected
- [ ] `size=None` does not break artefact selection or extension preference
- [ ] no-checksum project -> `checksum_source: none`, not failed
- [ ] URL-encoded project path (`group%2Fproject`) builds the correct endpoint
- [ ] `PRIVATE-TOKEN` auth header set correctly by the backend
- [ ] pagination across multiple release pages

---

## 7. References (verified)

- Release links API (assets are links; http/https/ftp; fields
  `name`/`url`/`direct_asset_url`/`link_type`):
  https://docs.gitlab.com/api/releases/links
- Direct asset URL form
  `https://host/namespace/project/releases/:release/downloads/:filepath`:
  GitLab docs, "Permanent links to release assets".

---

## 8. Definition of done

- `GitLabBackend` implements the 3-method contract, normalising releases and
  link assets (sources filtered, `direct_asset_url` preferred).
- `scm_release` supports `provider: gitlab` with `host`/`project_id`.
- Resolver code is unchanged.
- Test scenarios in §6 pass.
- Changelog fragment added; `github_release` shim untouched.
