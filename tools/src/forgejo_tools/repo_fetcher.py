import shutil
from pathlib import Path

from git import Repo
from packaging.version import InvalidVersion, Version


def fetch_ini_files(repo_url, target_path, raw_output_dir, temp_dir="/tmp/forgejo_repo_tmp"):
    temp_repo = Path(temp_dir)
    out_dir = Path(raw_output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    min_version = Version("7.0.0")

    if temp_repo.exists():
        repo = Repo(temp_repo)
        repo.git.fetch("--all", "--prune")
        repo.git.fetch("--tags")
    else:
        repo = Repo.clone_from(repo_url, temp_repo)

    valid_tags = []
    for tag in repo.tags:
        try:
            version = Version(tag.name.lstrip("v"))
        except InvalidVersion:
            # Tags ohne gültige Versionsnummer (z.B. 'nightly') ignorieren.
            continue
        if version >= min_version:
            valid_tags.append((version, tag))

    valid_tags.sort(key=lambda item: item[0])

    for _, tag in valid_tags:
        try:
            repo.git.checkout(tag)
        except Exception:
            continue

        path = temp_repo / target_path
        if not path.exists():
            print(f"Skipped: {tag.name} (missing {target_path})")
            continue

        # Ist es ein Verzeichnis? Dann alle *.ini kopieren
        if path.is_dir():
            ini_files = list(path.glob("*.ini"))
            if not ini_files:
                print(f"Skipped: {tag.name} (keine .ini in {target_path})")
            for ini in ini_files:
                dest = out_dir / f"{tag.name.replace('/', '_')}-{ini.name}"
                shutil.copy2(ini, dest)
            print(f"Fetched {len(ini_files)} .ini-Dateien für {tag.name}")
        # Oder ist es eine einzelne Datei?
        elif path.is_file():
            dest = out_dir / f"forgejo-{tag.name.replace('/', '_')}.ini"
            shutil.copy2(path, dest)
            print(f"Fetched: {tag.name}")
        else:
            print(f"Skipped: {tag.name} (unbekannter Pfadtyp)")
