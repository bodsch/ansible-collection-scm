import datetime
import hashlib
import os
import re
from collections import OrderedDict
from typing import Dict, Optional, Sequence

DEFAULT_IGNORE_KEYS = {"security": ["INTERNAL_TOKEN"], "oauth2": ["JWT_SECRET"]}


class ForgejoIni:
    """
    Ein minimalistischer INI-Parser, der
    - Keys VOR jeder Section (Default-Bereich) ebenfalls erfasst,
    - beim Einlesen alle ignore_keys (pro Section) direkt entfernt,
    - inline-Semikolon NICHT als Kommentar missversteht,
    - und später beim Schreiben Default-Keys ohne Header und dann
      jede Section mit einem Blankline-Separator ausgibt.
    """

    def __init__(self, module, path, ignore_keys=None):
        """
        Liest beim Anlegen sofort den Inhalt von 'path' ein
        und filtert alle ignorierten Keys direkt heraus.

        :param path: Pfad zur INI-Datei
        :param ignore_keys: Dict: Sektion → Liste von Schlüsseln, die rausfliegen sollen
        """
        self.module = module
        # self.module.log(f"ForgejoIni::__init__(path: {path}, ignore_keys: {ignore_keys})")

        self.path = path
        self.ignore_keys = ignore_keys or {}
        # data: OrderedDict[str(section) → dict[str(key)→str(value)]]
        # Wir verwenden OrderedDict, um Einfügereihenfolge zu wahren. Später sortieren wir beim Schreiben.
        self.data = OrderedDict()
        self._load()

    def _load(self):
        """
        Liest die INI-Datei zeilenweise ein und füllt self.data.
        - Eine Zeile, die mit ';' oder '#' beginnt, ist ein Kommentar.
        - Inline-Semikolon wird NICHT als Kommentar erkannt, wenn der Wert es enthält.
        - Keys vor der ersten Section landen in '__default__'.
        """
        current_section = "__default__"
        self.data[current_section] = {}

        # Regex für Section-Header: [irgendwas]
        section_pattern = re.compile(r"^\s*\[(?P<name>[^]]+)\]\s*$")
        # Regex für Key=Value: split an erstem '='
        kv_pattern = re.compile(r"^\s*(?P<key>[^=]+?)\s*=\s*(?P<val>.*)$")

        with open(self.path, "r", encoding="utf-8") as f:
            for raw_line in f:
                line = raw_line.rstrip("\n")

                # 1) Leerzeile → überspringen
                if not line.strip():
                    continue

                # 2) Kommentarzeile → überspringen
                stripped = line.lstrip()
                if stripped.startswith(";") or stripped.startswith("#"):
                    continue

                # 3) Section-Header?
                m_sec = section_pattern.match(line)
                if m_sec:
                    sec_name = m_sec.group("name").strip()
                    current_section = sec_name
                    if sec_name not in self.data:
                        self.data[sec_name] = {}
                    continue

                # 4) Key=Value?
                m_kv = kv_pattern.match(line)
                if m_kv:
                    key = m_kv.group("key").strip()
                    val = m_kv.group("val")
                    # Prüfen, ob key in ignore_keys[current_section] steht
                    if (
                        current_section in self.ignore_keys
                        and key in self.ignore_keys[current_section]
                    ):
                        # ignorieren
                        continue
                    # Ansonsten übernehmen
                    self.data[current_section][key] = val
                    continue

                # 5) Alles andere (z.B. fehlerhafte Zeile) ignorieren
                #    Bei Bedarf hier Logausgabe einfügen.
                continue

        # Wenn der Default-Bereich hinterher komplett leer ist, können wir ihn entfernen,
        # damit wir ihn später nicht unnötig schreiben.
        if not self.data["__default__"]:
            del self.data["__default__"]

    def checksum_section(self, section: str) -> str:
        """
        Berechnet SHA256 über alle normalisierten 'key = value\\n'-Zeilen der Sektion.
        Fehlende oder leere Sektionen ergeben denselben Hash (SHA256 über "").
        """
        items = self.normalize(self.data.get(section, {}))
        checksum = self._calc_checksum(items)

        return checksum

    def write(self, output_path):
        """
        wird von merge() aufgerufen.

        Schreibt self.data in eine INI-Datei:
        1. Erst alle Keys aus '__default__' (falls vorhanden), ohne Header.
        2. Dann je Section sortiert: eine Leerzeile, [Section], dann keys.
        3. Innerhalb jeder Sektion Keys alphabetisch.
        """
        with open(output_path, "w", encoding="utf-8") as f:
            # 1) Default-Keys (ohne Header) ganz vorne
            if "__default__" in self.data:
                for key in sorted(self.data["__default__"]):
                    val = self.data["__default__"][key]
                    f.write(f"{key} = {val}\n")
                # Leerzeile nach Default-Block, sofern es noch benannte Sections gibt
                if len(self.data) > 1:
                    f.write("\n")

            # 2) Alle benannten Sections alphabetisch
            for section in sorted(k for k in self.data if k != "__default__"):
                f.write(f"[{section}]\n")
                for key in sorted(self.data[section]):
                    val = self.data[section][key]
                    f.write(f"{key} = {val}\n")
                # Leerzeile zwischen den Sections (aber nicht nach der letzten Section)
                f.write("\n")

            # Das letzte zusätzliche "\n" kann man optional weglassen:
            # Wer ganz genau will, darf hier ein rstrip() auf den File-Inhalt anwenden.
            # aktiviere es hier, wenn du keine trailing blank line möchtest:
            # f.seek(0)
            # content = f.read().rstrip("\n")
            # f.seek(0)
            # f.write(content)

    def create_backup(self, config_file):
        """
        wird von merge() aufgerufen.
        """
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M")
        basename, ext = os.path.splitext(config_file)
        backup_config = f"{basename}_{timestamp}{ext}"

        os.rename(config_file, backup_config)

    @staticmethod
    def _calc_checksum(items: dict) -> str:
        """
        Berechnet SHA256 über sortierte 'key = value\\n'-Zeilen eines Dicts.
        Ersetzt die duplizierte Inline-Logik in merge() und checksum_section().
        """
        parts = [f"{key} = {items[key]}\n" for key in sorted(items)]
        return hashlib.sha256("".join(parts).encode("utf-8")).hexdigest()

    @classmethod
    def merge(cls, module, base_path, new_path, output_path, ignore_keys=None):
        """
        Merged base_path und new_path.

        Semantik der Sektionsexistenz:
          - new_config ist autoritativ: Sektionen, die NUR in base existieren,
            werden nicht übernommen (= gelöschte Sektionen verschwinden).
          - Sektionen, die nur in new existieren, werden übernommen (= neue Sektionen).
          - Bei gleichen Checksums wird base beibehalten (Stabilität).
        """
        # module.log(
        #     f"ForgejoIni::merge(base_path: {base_path}, new_path: {new_path}, output_path: {output_path}, ignore_keys: {ignore_keys})"
        # )

        ignore_keys = ignore_keys or {}

        base_ini = cls(module, base_path, ignore_keys)
        new_ini = cls(module, new_path, ignore_keys)

        merged_data = OrderedDict()

        # Nur über new_ini iterieren → base-only Sektionen fallen raus
        for section in sorted(new_ini.data.keys()):
            items_base = base_ini.data.get(section, {})
            items_new = new_ini.data.get(section, {})

            cs_base = cls._calc_checksum(items_base)
            cs_new = cls._calc_checksum(items_new)

            merged_data[section] = (
                items_new.copy() if cs_base != cs_new else items_base.copy()
            )

        merged_ini = cls.__new__(cls)
        merged_ini.module = module
        merged_ini.data = merged_data
        merged_ini.ignore_keys = ignore_keys

        merged_ini.create_backup(base_path)
        merged_ini.write(output_path)

    def sections_as_json(
        self,
        sections: Optional[Sequence[str]] = None,
        *,
        include_default: bool = False,
        include_missing: bool = True,
        indent: Optional[int] = 2,
    ) -> str:
        """
        Export selected INI sections as a JSON string.

        This is a read-only helper that serializes the currently loaded configuration
        (`self.data`) into JSON. It does not modify the internal representation.

        Args:
            sections:
                Section names to export. If None, all named sections are exported.
                The special '__default__' section is only included when `include_default=True`.
            include_default:
                If True and '__default__' exists, include it in the JSON output.
            include_missing:
                If True, requested sections that are not present in the INI are included
                as empty objects.
            indent:
                Indentation level for pretty printing. Use None for compact JSON.

        Returns:
            A JSON string mapping section names to key/value mappings.

        Examples:
            Export two sections:
                ini.sections_as_json(["server", "database"])

            Export all sections (except '__default__'):
                ini.sections_as_json()

            Include default keys:
                ini.sections_as_json(["server"], include_default=True)
        """
        # self.module.log(
        #     f"ForgejoIni::sections_as_json("
        #     f"sections: {sections}, include_default: {include_default}, include_missing: {include_missing}, indent: {indent})"
        # )

        # Determine which sections to export (preserve caller order if provided).
        if sections is None:
            requested = [s for s in self.data.keys() if s != "__default__"]
        else:
            requested = list(sections)

        payload: "OrderedDict[str, Dict[str, str]]" = OrderedDict()

        if include_default and "__default__" in self.data:
            payload["__default__"] = dict(self.data["__default__"])

        for sec in requested:
            if sec == "__default__":
                # Only include via include_default to avoid surprises.
                if (
                    include_default
                    and "__default__" in self.data
                    and "__default__" not in payload
                ):
                    payload["__default__"] = dict(self.data["__default__"])
                continue

            if sec in self.data:
                # Keep deterministic key order: sort keys (matches existing checksum/write approach).
                items = self.data[sec]
                payload[sec] = {k: items[k] for k in sorted(items)}
            else:
                if include_missing:
                    payload[sec] = {}

        return payload

    def normalize(self, section_items):
        """ """
        if isinstance(section_items, dict):
            return {k: self.normalize(section_items[k]) for k in sorted(section_items)}

        if isinstance(section_items, list):
            return [self.normalize(x) for x in section_items]

        if isinstance(section_items, tuple):
            return tuple(self.normalize(x) for x in section_items)

        return section_items
