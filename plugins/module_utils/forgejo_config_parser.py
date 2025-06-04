
# import os
import re
import hashlib
# import datetime
# import shutil
from collections import OrderedDict

# Beispiel für DEFAULT_IGNORE_KEYS
DEFAULT_IGNORE_KEYS = {
    "security": ["INTERNAL_TOKEN"],
    "oauth2": ["JWT_SECRET"]
}


class ForgejoConfigParser:
    """
    """

    def __init__(self, module, path, ignore_keys=None):
        """
        Liest beim Anlegen sofort den Inhalt von 'path' ein und filtert
        alle ignorierten Keys direkt heraus.

        :param path: Pfad zur INI-Datei
        :param ignore_keys: Dict: Sektion → Liste von Schlüsseln, die rausfliegen sollen
        """
        self.module = module
        self.module.log(f"ForgejoConfigParser::__ini__({path}, {ignore_keys})")

        self.path = path
        self.ignore_keys = ignore_keys or {}
        # data: OrderedDict[ str(section) → dict[str(key)→str(value)] ]
        self.data = OrderedDict()
        self._load()

    def _load(self):
        """
        Liest die INI-Datei zeilenweise ein und füllt self.data.
        Kommentare werden nur dann verworfen, wenn die Zeile mit ';' oder '#' beginnt.
        Inline-Semikolon in einem Wert bleibt Teil von 'value'.
        """
        self.module.log("ForgejoConfigParser::_load()")
        current_section = None

        # Regex, um eine Section-Zeile zu erkennen
        section_pattern = re.compile(r'^\s*\[(?P<name>[^]]+)\]\s*$')
        # Regex, um ein key=value zu erkennen (split auf erstes '=').
        kv_pattern = re.compile(r'^\s*(?P<key>[^=]+?)\s*=\s*(?P<val>.*)$')

        with open(self.path, 'r', encoding='utf-8') as f:
            for raw_line in f:
                line = raw_line.rstrip("\n")  # ohne Zeilenumbruch

                # 1) Leerzeile?
                if not line.strip():
                    continue

                # 2) Kommentarzeile? semikolon oder # am Zeilenanfang:
                if line.lstrip().startswith(';') or line.lstrip().startswith('#'):
                    continue

                # 3) Section-Header?
                m_sec = section_pattern.match(line)
                if m_sec:
                    sec_name = m_sec.group('name').strip()
                    current_section = sec_name
                    # lege neue Sektion mit leerem dict an (wenn noch nicht da)
                    if sec_name not in self.data:
                        self.data[sec_name] = {}
                    continue

                # 4) Key=Value?
                m_kv = kv_pattern.match(line)
                if m_kv and current_section is not None:
                    key = m_kv.group('key').strip()
                    val = m_kv.group('val')
                    # Direkt nachladen, ob key in ignore_keys[current_section] steht:
                    if current_section in self.ignore_keys \
                       and key in self.ignore_keys[current_section]:
                        # ignorieren
                        continue

                    # Wert so übernehmen, wie er da steht (z.B. "text/html; charset=utf-8")
                    self.data[current_section][key] = val
                    continue

                # Wenn wir hierher kommen, war's weder Section noch Key=Value noch Kommentar.
                # Das können wir nach Bedarf entweder ignorieren oder als 'rohe Zeile' speichern.
                # Für diesen Anwendungsfall ignorieren wir sie stillschweigend.
                continue

    def checksum_section(self, section):
        """
        Berechnet SHA256 über die geordnete Key=Value-Liste dieser Sektion.
        """
        self.module.log(f"ForgejoConfigParser::checksum_section({section})")

        parts = []
        for key in sorted(section):
            val = section[key]
            parts.append(f"{key} = {val}\n")
        return hashlib.sha256("".join(parts).encode("utf-8")).hexdigest()

        # items = self.data.get(section, {})  # → {} wenn sektion fehlt
        # # Jetzt sortieren und Hash über "" bzw. Keys bauen:
        # parts = []
        # for key in sorted(items):
        #     val = items[key]
        #     parts.append(f"{key} = {val}\n")
        # joined = "".join(parts).encode("utf-8")
        # return hashlib.sha256(joined).hexdigest()

        # if section not in self.data:
        #     return None
        # # Baue einen eindeutigen String: "key = value\n" pro Key, sortiert nach key.
        # parts = []
        # for key in sorted(self.data[section]):
        #     val = self.data[section][key]
        #     parts.append(f"{key} = {val}\n")
        # joined = "".join(parts).encode("utf-8")
        # return hashlib.sha256(joined).hexdigest()

    def write(self, output_path):
        """
        Schreibt self.data in eine neue INI-Datei, Sections alphabetisch,
        Keys alphabetisch, OHNE Leerzeilen dazwischen.
        """
        # self.module.log(f"ForgejoConfigParser::write({output_path})")
        with open(output_path, 'w', encoding='utf-8') as f:
            for section in sorted(self.data):
                f.write(f"[{section}]\n")
                for key in sorted(self.data[section]):
                    val = self.data[section][key]
                    f.write(f"{key} = {val}\n")
                # KEIN zusätzliches f.write("\n")

    @classmethod
    def merge(cls, module, base_path, new_path, output_path, ignore_keys=None):
        """
        Liest base_path und new_path jeweils mit SimpleIni ein,
        entfernt bereits während des Einlesens alle ignore_keys,
        führt dann pro Sektion den Merge durch:

        - Wenn Sektion nur in base ist -> beibehalten.
        - Wenn Sektion nur in new  -> übernehmen.
        - Wenn Sektion in beiden → SHA256 vergleichen:
            • identisch → base behalten
            • unterschiedlich → new übernehmen

        Das Resultat wird alphabetisch sortiert in output_path geschrieben.

        Gibt zurück: (changed, details)
        """
        module = module
        module.log(f"ForgejoConfigParser::merge({base_path}, {new_path} {output_path}, {ignore_keys})")

        ignore_keys = ignore_keys or {}
        base_ini = cls(module, base_path, ignore_keys)
        new_ini = cls(module, new_path, ignore_keys)

        # Alle Sektionen zusammentragen
        all_sections = set(base_ini.data.keys()) | set(new_ini.data.keys()) | set(ignore_keys.keys())

        result = OrderedDict()
        changed = False

        for section in sorted(all_sections):
            base_sec = base_ini.data.get(section, {})
            new_sec = new_ini.data.get(section, {})
            # beide Sektionen ggf. nach Entfernen der ignorierten Keys bereits bereinigt,
            # weil der Konstruktor ignore_keys schon berücksichtigt hat.

            if section in new_ini.data:
                # Sektion existiert in new - vergleichen
                if section in base_ini.data:
                    # beide da → checksum prüfen
                    cs_base = base_ini.checksum_section(section)
                    cs_new = new_ini.checksum_section(section)
                    if cs_base != cs_new:
                        result[section] = new_sec.copy()
                        changed = True
                    else:
                        # unverändert
                        result[section] = base_sec.copy()
                else:
                    # Sektion nur in new → übernehmen
                    result[section] = new_sec.copy()
                    changed = True
            else:
                # Sektion nicht in new → nur in base
                result[section] = base_sec.copy()
                # changed bleibt False (weil nichts Neues da ist)

            # Falls die Sektion weder in base noch new existiert, aber in ignore_keys war,
            # legen wir sie trotzdem als leere Sektion an:
            if section not in base_ini.data and section not in new_ini.data:
                result[section] = {}  # leere Sektion

        # Anschließend schreiben
        merged_ini = cls.__new__(cls)         # Dummy‐Instanz ohne __init__ aufrufen
        merged_ini.data = result
        merged_ini.ignore_keys = ignore_keys
        merged_ini.write(output_path)

        return changed

# # Beispiel, wie man es in der Run-Methode einsetzen könnte:
# def run(self):
#     """
#     Annahme: self.config ist Pfad zu forgejo.ini, self.new_config zu forgejo.new,
#     self.ignore_map ist das Dict für ignore_keys, self.owner/group usw. existieren.
#     """
#     result = dict(failed=False, changed=False, msg="forgejo.ini is up-to-date.")
#
#     # 1) Wenn config nicht existiert: neu kopieren
#     if not os.path.exists(self.config):
#         shutil.copyfile(self.new_config, self.config)
#         shutil.chown(self.config, self.owner, self.group)
#         return dict(failed=False, changed=True, msg="forgejo.ini was created successfully.")
#
#     # 2) Sonst manuell beide Dateien einlesen, OHNE ConfigParser
#     base = SimpleIni(self.config, ignore_keys=self.ignore_map)
#     new  = SimpleIni(self.new_config, ignore_keys=self.ignore_map)
#
#     # 3) Prüfen, ob sich irgendetwas geändert hat:
#     #    Wir vergleichen pro Sektion die Checksummen – oder einfach den zusammengebauten Text.
#     changed = False
#     for sektion in set(base.data.keys()) | set(new.data.keys()) | set(self.ignore_map.keys()):
#         cs_base = base.checksum_section(sektion)
#         cs_new  = new.checksum_section(sektion)
#         # Falls cs_base != cs_new (None vs Wert oder zwei unterschiedliche Hashes),
#         # ist changed=True.
#         if cs_base != cs_new:
#             changed = True
#             break
#
#     if not changed:
#         return result
#
#     # 4) Wenn geändert: Backup anlegen, mergen, zurückkopieren
#     timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M")
#     basename, ext = os.path.splitext(self.config)
#     backup_config = f"{basename}_{timestamp}{ext}"
#     merged_path  = os.path.join(os.path.dirname(self.config), "forgejo.merged")
#
#     # Backup
#     os.rename(self.config, backup_config)
#
#     # Merge und Schreiben
#     SimpleIni.merge(
#         base_path=self.config,      # der ursprüngliche Pfad existiert gerade nicht mehr,
#         #                weil wir es umbenannt haben → wir müssen hier auf backup_config verweisen!
#         new_path=self.new_config,
#         output_path=merged_path,
#         ignore_keys=self.ignore_map
#     )
#
#     # Da wir base_path=forgejo.ini angegeben haben, ist das falsch:
#     # Tatsächlich müssen wir natürlich das Backup (backup_config) als Basis verwenden.
#     # Also besser:
#     SimpleIni.merge(
#         base_path=backup_config,
#         new_path=self.new_config,
#         output_path=merged_path,
#         ignore_keys=self.ignore_map
#     )
#
#     # merged_path nach forgejo.ini kopieren
#     shutil.copyfile(merged_path, self.config)
#     shutil.chown(self.config, self.owner, self.group)
#
#     return dict(failed=False, changed=True, msg="forgejo.ini was changed.")


# # ------------------------------------
#
# import re
# import hashlib
# from io import StringIO
# from configparser import ConfigParser
#
#
# DEFAULT_IGNORE_KEYS = {
#     "security": ["INTERNAL_TOKEN"],
#     "oauth2": ["JWT_SECRET"]
# }
#
#
# class ForgejoConfigParser:
#     def __init__(self, module, path, ignore_keys=None):
#         self.module = module
#
#         self.module.log(f"ForgejoConfigParser({path}, {ignore_keys})")
#
#         self.path = path
#         # Standard-Werte für ignore_keys in einer Konstanten ausgelagert
#         self.ignore_keys = ignore_keys if ignore_keys is not None else DEFAULT_IGNORE_KEYS
#         self._base_parser = self._create_parser()
#         self.raw = self._read_file()
#         self.parser = self._parse_config(self.raw)
#
#     @staticmethod
#     def _create_parser():
#         """
#         Hilfsfunktion, um überall denselben, korrekt konfigurierten ConfigParser zu erzeugen.
#         """
#         parser = ConfigParser(
#             strict=False,
#             delimiters=('=',),
#             interpolation=None,
#             inline_comment_prefixes=None   # <-- keine Inline-Kommentare mehr
#         )
#         parser.optionxform = str  # Groß-/Kleinschreibung der Schlüssel beibehalten
#         return parser
#
#     def _read_file(self):
#         with open(self.path, 'r', encoding='utf-8') as f:
#             return f.read()
#
#     def _parse_config(self, text):
#         """
#         Liest den Text (nach Preprocessing) in einen neuen Parser ein und gibt ihn zurück.
#         """
#         parser = self._create_parser()
#         parser.read_string(self._preprocess(text))
#         return parser
#
#     def _preprocess(self, text):
#         """
#         1. Entfernt überflüssige Leerzeilen.
#         2. Fügt bei Bedarf einen Dummy-Header [__default__] ein, falls
#            keine echte Section-Eröffnung am Anfang steht.
#         """
#         lines = [line for line in text.splitlines() if line.strip() != ""]
#         if lines and not lines[0].startswith('['):
#             lines.insert(0, '[__default__]')
#         return "\n".join(lines)
#
#     def _remove_ignored_keys(self, parser):
#         """
#         Entfernt in-place alle Schlüssel, die in ignore_keys definiert sind.
#         """
#         for section, keys in self.ignore_keys.items():
#             if parser.has_section(section):
#                 for key in keys:
#                     parser.remove_option(section, key)
#
#     # def get_cleaned_string(self):
#     #     """
#     #     1. Erzeugt einen frischen Parser und befüllt ihn mit allen aktuellen
#     #        Sektionen/Optionen aus self.parser.
#     #     2. Entfernt anschließend volatile/ignorierte Schlüssel.
#     #     3. Schreibt das Ergebnis in einen String und gibt ihn zurück.
#     #     """
#     #     temp = self._create_parser()
#     #     # read_dict liest alle Sections und Keys ein
#     #     temp.read_dict({sec: dict(self.parser.items(sec)) for sec in self.parser.sections()})
#     #
#     #     # Jetzt die ignoriere Schlüssel rauswerfen
#     #     self._remove_ignored_keys(temp)
#     #
#     #     # Dafür sorgen, dass alle Sektionen aus ignore_keys existieren (auch wenn leer)
#     #     for sec in self.ignore_keys:
#     #         if not temp.has_section(sec):
#     #             temp.add_section(sec)
#     #
#     #     output = StringIO()
#     #     temp.write(output)
#     #     return output.getvalue()
#
#     def get_cleaned_string(self):
#         """
#         1. Erzeugt einen frischen Parser und befüllt ihn mit allen aktuellen
#            Sektionen/Optionen aus self.parser.
#         2. Entfernt anschließend volatile/ignorierte Schlüssel.
#         3. Fügt alle in ignore_keys gelisteten Sektionen hinzu, falls sie fehlen.
#         4. Schreibt Sektionen und Keys alphabetisch sortiert (ohne Leerzeilen).
#         5. Gibt das Ergebnis als String zurück.
#         """
#         # 1) Basis-PARSER mit allen Sektionen/Keys aus self.parser füllen
#         temp = self._create_parser()
#         temp.read_dict({sec: dict(self.parser.items(sec)) for sec in self.parser.sections()})
#
#         # 2) Ignorierte Keys entfernen
#         self._remove_ignored_keys(temp)
#
#         # 3) Sicherstellen, dass auch leere Sektionen aus ignore_keys existieren
#         for sec in self.ignore_keys:
#             if not temp.has_section(sec):
#                 temp.add_section(sec)
#
#         # 4) Alphabetisch sortiert in einen String schreiben (ohne Leerzeilen)
#         output = StringIO()
#         for section in sorted(temp.sections()):
#             output.write(f"[{section}]\n")
#             for key, val in sorted(temp.items(section)):
#                 output.write(f"{key} = {val}\n")
#             # KEINE zusätzliche Ausgabe einer Leerzeile hier
#
#         return output.getvalue()
#
#     def checksum(self):
#         """
#         SHA256-Checksumme über den "gereinigten" Config-String.
#         """
#         cleaned = self.get_cleaned_string().encode('utf-8')
#         return hashlib.sha256(cleaned).hexdigest()
#
#     def is_equal_to(self, other):
#         """
#         Vergleicht die "gereinigten" Strings (ohne führende/trailing Leerzeilen).
#         """
#         self_clean = self.get_cleaned_string().strip()
#         other_clean = other.get_cleaned_string().strip()
#
#         self.module.log("-------------------------------------------")
#         self.module.log(f"{self_clean.splitlines()}")
#         self.module.log("-------------------------------------------")
#         self.module.log(f"{other_clean.splitlines()}")
#         self.module.log("-------------------------------------------")
#
#         return self_clean == other_clean
#
#     # def merge_into(self, base_path, output_path):
#     #     """
#     #     Führt die Konfiguration in self über base_path zusammen und speichert
#     #     das Ergebnis in output_path. Ignoriert hierbei bestimmte Schlüssel
#     #     (siehe self.ignore_keys). Sortiert Sektionen und Schlüssel alphabetisch.
#     #     """
#     #     self.module.log(f"ForgejoConfigParser::merge_into(self, {base_path}, {output_path})")
#     #
#     #     # 1) Basis-Konfiguration einlesen
#     #     base = ForgejoConfigParser(self.module, base_path, self.ignore_keys)
#     #
#     #     # 2) Neuen Parser für das Merge-Ergebnis erzeugen
#     #     merged = self._create_parser()
#     #
#     #     # 3) Werte aus base übernehmen
#     #     for section in base.parser.sections():
#     #         merged.add_section(section)
#     #         for key, val in base.parser.items(section):
#     #             merged.set(section, key, val)
#     #
#     #     # 4) Werte aus self (z.B. forgejo.new) übernehmen, volatile Keys überspringen
#     #     for section in self.parser.sections():
#     #         if not merged.has_section(section):
#     #             merged.add_section(section)
#     #
#     #         for key, val in self.parser.items(section):
#     #             if section in self.ignore_keys and key in self.ignore_keys[section]:
#     #                 continue
#     #             merged.set(section, key, val)
#     #
#     #     # 5) In-Memory-Zusammenführung in String schreiben (ohne doppeltes File-I/O)
#     #     buffer = StringIO()
#     #     self._write_sorted_config(merged, buffer)
#     #     content = buffer.getvalue()
#     #
#     #     # 6) [__default__]-Header entfernen, falls vorhanden
#     #     content = re.sub(r'^\[__default__\]\n', '', content, flags=re.MULTILINE)
#     #
#     #     self.module.log(content.splitlines())
#     #
#     #     # 7) Endgültig in output_path schreiben
#     #     with open(output_path, 'w', encoding='utf-8') as f:
#     #         f.write(content)
#
#     def merge_into(self, base_path, output_path):
#         """
#         Führt die Konfiguration in self über base_path zusammen und speichert
#         das Ergebnis in output_path. Ignoriert hierbei Schlüssel aus self.ignore_keys.
#         Sortiert alle Sektionen und Keys alphabetisch und schreibt am Ende
#         ein sauberes, leerzeilenfreies File.
#         """
#         self.module.log(f"ForgejoConfigParser::merge_into(self, {base_path}, {output_path})")
#
#         # 1) Base-Parser einlesen
#         base = ForgejoConfigParser(self.module, base_path, self.ignore_keys)
#
#         # 2) Neue (self-)Instanz soll über base „drüber“ gemerged werden
#         new = self  # self.parser ist bereits auf die „neue“ Datei geladen
#
#         # 3) Helferfunktion: Erzeuge aus einem Dict von key→value einen String
#         #    (eine Zeile pro key), sortiert nach key, und gib die SHA256-Checksumme zurück.
#         def section_checksum(items_dict):
#             # "key = value\n" für jeden key in sortierter Reihenfolge
#             s = "".join(f"{k} = {v}\n" for k, v in sorted(items_dict.items()))
#             return hashlib.sha256(s.encode("utf-8")).hexdigest()
#
#         # 4) Sammle alle relevanten Sections:
#         #    – aus base.parser.sections()
#         #    – aus new.parser.sections()
#         #    – aus den Keys von ignore_keys (damit leere Ignored-Sections trotzdem angelegt werden)
#         all_sections = (
#             set(base.parser.sections())
#             | set(new.parser.sections())
#             | set(self.ignore_keys.keys())
#         )
#
#         # 5) Lege einen frischen Parser an, in den wir das Ergebnis schreiben
#         merged = self._create_parser()
#
#         # 6) Pro Section entscheiden, ob wir base behalten oder new übernehmen:
#         for section in sorted(all_sections):
#             # --- a) Items von base (ohne ignore_keys) extrahieren ---
#             base_items = {}
#             if base.parser.has_section(section):
#                 base_items = dict(base.parser.items(section))
#                 if section in self.ignore_keys:
#                     for ign in self.ignore_keys[section]:
#                         base_items.pop(ign, None)
#
#             # --- b) Items von new (ohne ignore_keys) extrahieren ---
#             new_items = {}
#             if new.parser.has_section(section):
#                 new_items = dict(new.parser.items(section))
#                 if section in self.ignore_keys:
#                     for ign in self.ignore_keys[section]:
#                         new_items.pop(ign, None)
#
#             # --- c) Check, ob new_items vorhanden und anders als base_items ---
#             changed = False
#             if section in new.parser.sections():
#                 # Wenn Section in base UND in new existiert, vergleiche Checksummen
#                 if section in base.parser.sections():
#                     cs_base = section_checksum(base_items)
#                     cs_new = section_checksum(new_items)
#                     changed = (cs_base != cs_new)
#                 else:
#                     # Section nur in new vorhanden → auf jeden Fall „geändert“
#                     changed = True
#
#             # --- d) Entscheide, welche Items wir in merged setzen ---
#             if changed:
#                 chosen = new_items
#             else:
#                 chosen = base_items
#
#             # --- e) Section im merged-Parser anlegen und gefundene Items setzen ---
#             merged.add_section(section)
#             for key, val in sorted(chosen.items()):
#                 merged.set(section, key, val)
#
#         # 7) Jetzt merged-Parser in einen String schreiben (alphabetisch sortiert)
#         buffer = StringIO()
#         self._write_sorted_config(merged, buffer)
#         content = buffer.getvalue()
#
#         # 8) [__default__]-Header (Dummy) entfernen, falls vorhanden
#         content = re.sub(r'^\[__default__\]\n', '', content, flags=re.MULTILINE)
#
#         # 9) In die Ausgabedatei schreiben
#         with open(output_path, "w", encoding="utf-8") as f:
#             f.write(content)
#
#     @staticmethod
#     def _write_sorted_config(parser, file_like):
#         """
#         Schreibt alle Sektionen und deren Schlüssel/Werte alphabetisch sortiert
#         (Sektionen nach Name, Keys pro Sektion nach Name).
#         """
#         for section in sorted(parser.sections()):
#             file_like.write(f"[{section}]\n")
#             for key, value in sorted(parser.items(section)):
#                 file_like.write(f"{key} = {value}\n")
#             file_like.write("\n")
#
