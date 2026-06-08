#!/usr/bin/python3

import hashlib
import re
from pathlib import Path

from forgejo_tools.colors import bcolors


class ForgejoConfigDiff:
    def __init__(self, base_path):
        self.base_dir = Path(base_path)

    def run(self):
        """
        Vergleicht alle versionierten ``.ini``-Dateien im ``base_dir``.

        Für jede Version wird die jeweils unmittelbar nächste Version
        betrachtet:

        * Liegt sie in derselben ``major.minor`` mit höherer Patch-Nummer,
          wird ein Patch-Diff ausgegeben.
        * Ist sie die erste Version einer höheren Minor/Major, wird ein
          Minor-Diff ausgegeben (somit genau einmal pro Minor-Sprung, von der
          letzten Patch-Version der alten Minor zur ersten der neuen).
        """
        versions = []
        for f in self.base_dir.iterdir():
            if f.suffix != ".ini":
                continue
            version = self.parse_version(f.name)
            if version:
                versions.append((version, f))

        versions.sort(key=lambda item: item[0])
        checksum_map = {f: self.sha256sum(f) for _, f in versions}

        for i, (ver1, f1) in enumerate(versions[:-1]):
            ver2, f2 = versions[i + 1]

            # Identische Dateien überspringen.
            if checksum_map[f1] == checksum_map[f2]:
                continue

            if ver2[:2] == ver1[:2] and ver2[2] > ver1[2]:
                print(bcolors.bold(
                    f"--- Diff zwischen Patch-Versionen: {f1.name} -> {f2.name} ---"
                ))
                self.compare(f1, f2)
            elif ver2[:2] != ver1[:2]:
                print(bcolors.bold(
                    f"=== Diff zur nächsten Minor-Version: {f1.name} -> {f2.name} ==="
                ))
                self.compare(f1, f2)

    def compare(self, file1: Path, file2: Path):
        cfg1 = self.read_ini_with_comments(file1)
        cfg2 = self.read_ini_with_comments(file2)

        all_sections = sorted(set(cfg1.keys()) | set(cfg2.keys()))

        for section in all_sections:
            keys1 = cfg1.get(section, {})
            keys2 = cfg2.get(section, {})

            all_keys = sorted(set(keys1.keys()) | set(keys2.keys()))

            diff_output = []

            for key in all_keys:
                v1 = keys1.get(key)
                v2 = keys2.get(key)

                if v1 == v2:
                    continue

                if v1 is None:
                    diff_output.append(f"  {bcolors.dark_green('+')} {key} = {v2[0]}")
                elif v2 is None:
                    diff_output.append(f"  {bcolors.dark_red('-')} {key} = {v1[0]}")
                else:
                    diff_output.append(
                        f"  {bcolors.color('~', bcolors.YELLOW)} {key} = "
                        f"{self._format_change(v1, v2)}"
                    )

            # Nur Sektionen mit tatsächlichem Inhalt ausgeben.
            if diff_output:
                print(f"[{section}]")
                print('\n'.join(diff_output))

    @staticmethod
    def _format_change(v1, v2):
        """
        Beschreibt die Änderung eines Schlüssels, der in beiden Versionen
        existiert. ``v1``/``v2`` sind Tupel ``(wert, is_commented)``.

        Es wird die Wertänderung dargestellt und – falls relevant – ein
        Wechsel des Kommentar-Status (auskommentierter Default <-> aktiv).
        """
        parts = []
        if v1[0] != v2[0]:
            parts.append(f"{v1[0]} → {v2[0]}")
        else:
            parts.append(v1[0])

        if v1[1] != v2[1]:
            state_old = "auskommentiert" if v1[1] else "aktiv"
            state_new = "auskommentiert" if v2[1] else "aktiv"
            parts.append(f"({state_old} → {state_new})")

        return " ".join(parts)

    def read_ini_with_comments(self, path: Path):
        """
        Liest eine INI-Datei inkl. auskommentierter Sektionen und Einträge.

        Forgejos ``app.example.ini`` kommentiert sowohl Default-Werte als auch
        ganze Sektionen mit ``;`` aus. Führende Kommentarzeichen (``;``/``#``)
        werden daher entfernt, bevor die Zeile als Sektion oder ``key=value``
        interpretiert wird.

        Gibt zurück: ``dict[section][key] = (value, is_commented)``.
        """
        config = {}
        current_section = '__global__'
        config[current_section] = {}

        with path.open(encoding='utf-8') as f:
            for line in f:
                stripped = line.strip()

                if not stripped:
                    continue

                is_commented = stripped[0] in ';#'
                content = stripped.lstrip(';#').strip() if is_commented else stripped

                if content.startswith('[') and content.endswith(']'):
                    current_section = content[1:-1]
                    config.setdefault(current_section, {})
                    continue

                if '=' in content:
                    key, val = map(str.strip, content.split('=', 1))
                    config.setdefault(current_section, {})[key] = (val, is_commented)

        return config

    def sha256sum(self, path):
        h = hashlib.sha256()
        with open(path, 'rb') as f:
            while chunk := f.read(8192):
                h.update(chunk)
        return h.hexdigest()

    def parse_version(self, filename):
        match = re.search(r'v(\d+)\.(\d+)\.(\d+)', filename)
        if match:
            return tuple(map(int, match.groups()))
        return None
