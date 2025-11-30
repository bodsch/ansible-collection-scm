import datetime
import hashlib
import os
import re

# import shutil
from collections import OrderedDict

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
        # self.module.log(f"ForgejoIni::__init__({path}, {ignore_keys})")

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

    def checksum_section(self, section):
        """
        Berechnet SHA256 über alle "key = value\n"-Zeilen in der Sektion.
        Fehlende oder komplett leere Sektion geben denselben Hash (SHA256 über "") zurück.
        """
        # self.module.log(f"ForgejoIni::checksum_section({section})")

        items = self.data.get(section, {})  # {} falls fehlt oder leer
        parts = []
        for key in sorted(items):
            val = items[key]
            parts.append(f"{key} = {val}\n")
        joined = "".join(parts).encode("utf-8")
        return hashlib.sha256(joined).hexdigest()

    def write(self, output_path):
        """
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
        """ """
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M")
        basename, ext = os.path.splitext(config_file)
        backup_config = f"{basename}_{timestamp}{ext}"

        os.rename(config_file, backup_config)

    @classmethod
    def merge(cls, module, base_path, new_path, output_path, ignore_keys=None):
        """
        Liest base_path und new_path jeweils mit ForgejoIni ein,
        filtert laufend ignore_keys heraus
        und erzeugt in output_path das Merge-Ergebnis:

        - Default-Keys (vor jeder Section) behandeln wir als eigene "Section" '__default__'.
          Fehlende vs. leere Default → gleicher Hash.
        - Für jede Section (inkl. '__default__') vergleichen wir:
            • nur in base → übernehmen
            • nur in new  → übernehmen
            • in beiden  → Hash vergleichen:
                 – gleich → base übernehmen
                 – ungleich → new übernehmen
        - Im Write: Default-Block ganz vorne ohne Header, danach jede Section mit Header,
          getrennt durch Leerzeilen.
        """
        # module.log(f"ForgejoIni::merge({base_path}, {new_path}, {output_path}, {ignore_keys})")

        ignore_keys = ignore_keys or {}
        base_ini = cls(module, base_path, ignore_keys)
        new_ini = cls(module, new_path, ignore_keys)

        # 1) Alle möglichen Sektionen zusammentragen,
        #    inklusive '__default__' und alle keys aus ignore_keys
        all_sections = (
            set(base_ini.data.keys())
            | set(new_ini.data.keys())
            | set(ignore_keys.keys())
        )

        merged_data = OrderedDict()
        for section in sorted(all_sections):
            # Items holen ({} falls fehlt)
            items_base = base_ini.data.get(section, {})
            items_new = new_ini.data.get(section, {})

            # Hash-Funktion wie oben
            def calc_checksum(items_dict):
                parts = []
                for key in sorted(items_dict):
                    val = items_dict[key]
                    parts.append(f"{key} = {val}\n")
                return hashlib.sha256("".join(parts).encode("utf-8")).hexdigest()

            cs_base = calc_checksum(items_base)
            cs_new = calc_checksum(items_new)

            # Entscheiden, was wir übernehmen:
            if section in base_ini.data and section not in new_ini.data:
                merged_data[section] = items_base.copy()
            elif section not in base_ini.data and section in new_ini.data:
                merged_data[section] = items_new.copy()
            else:
                # in beiden vorhanden
                if cs_base == cs_new:
                    merged_data[section] = items_base.copy()
                else:
                    merged_data[section] = items_new.copy()

            # Wenn section weder in base noch in new war, aber in ignore_keys existiert:
            # lege sie trotzdem als leere Sektion an (falls gewünscht). Soll das nicht passieren,
            # kommentiere die nächste Zeile aus:
            if section not in base_ini.data and section not in new_ini.data:
                merged_data[section] = {}

        # 2) Dummy-Instanz erzeugen, damit wir .data setzen und write() nutzen können
        merged_ini = cls.__new__(cls)
        merged_ini.data = merged_data
        merged_ini.ignore_keys = ignore_keys

        merged_ini.create_backup(base_path)

        # 3) In output_path schreiben
        merged_ini.write(output_path)
