
import re
import hashlib
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
