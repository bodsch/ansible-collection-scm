
import re
import hashlib
from io import StringIO

try:
    from configparser import ConfigParser
except ImportError:
    # ver. < 3.0
    from ConfigParser import ConfigParser


class ForgejoConfigParser:
    def __init__(self, path, ignore_keys=None):
        self.path = path
        self.ignore_keys = ignore_keys or {
            "security": ["INTERNAL_TOKEN"],
            "oauth2": ["JWT_SECRET"]
        }
        self.raw = self._read_file()
        self.parser = self._parse_config(self.raw)

    def _read_file(self):
        with open(self.path, 'r', encoding='utf-8') as f:
            return f.read()

    def _parse_config(self, text):
        parser = ConfigParser(strict=False, delimiters=('='), interpolation=None)
        parser.optionxform = str
        parser.read_string(self._preprocess(text))
        return parser

    def _preprocess(self, text):
        """
        """
        # Entferne Leerzeilen (auch mehrfach aufeinanderfolgende) vor dem Parsen
        lines = text.splitlines()
        lines = [line for line in lines if line.strip() != '']

        if lines and not lines[0].startswith('['):
            lines.insert(0, '[__default__]')

        return '\n'.join(lines)

        # if not text.strip().startswith('['):
        #     text = '[__default__]\n' + text
        #
        # return text

    def _remove_ignored_keys(self, parser):
        """
        """
        for section, keys in self.ignore_keys.items():
            if parser.has_section(section):
                for key in keys:
                    parser.remove_option(section, key)

    def get_cleaned_string(self):
        temp_parser = ConfigParser(strict=False, delimiters=('='), interpolation=None)
        temp_parser.optionxform = str
        temp_parser.read_dict({s: dict(self.parser.items(s)) for s in self.parser.sections()})

        self._remove_ignored_keys(temp_parser)

        for section in self.ignore_keys:
            if not temp_parser.has_section(section):
                temp_parser.add_section(section)

        output = StringIO()
        temp_parser.write(output)
        return output.getvalue()

    def checksum(self):
        return hashlib.sha256(self.get_cleaned_string().encode('utf-8')).hexdigest()

    def is_equal_to(self, other):
        """
        """
        self_clean = self.get_cleaned_string().strip()
        other_clean = other.get_cleaned_string().strip()

        return self_clean == other_clean

    def merge_into(self, base_path, output_path):
        base = ForgejoConfigParser(base_path, self.ignore_keys)
        merged = ConfigParser(strict=False, delimiters=('='), interpolation=None)
        merged.optionxform = str

        # Start mit den Werten aus base
        for section in base.parser.sections():
            merged.add_section(section)
            for key, val in base.parser.items(section):
                merged.set(section, key, val)

        # Werte aus self (z. B. forgejo.new) übernehmen
        for section in self.parser.sections():
            if not merged.has_section(section):
                merged.add_section(section)

            for key, val in self.parser.items(section):
                if section in self.ignore_keys and key in self.ignore_keys[section]:
                    continue  # Skip volatile keys
                merged.set(section, key, val)

        # Schreibe merged Datei
        with open(output_path, 'w', encoding='utf-8') as f:
            # merged.write(f)
            self.write_sorted_config(merged, f)

        # Nach write()
        with open(output_path, 'r', encoding='utf-8') as f:
            content = f.read()

        # Entferne [__default__] Section Header
        content = re.sub(r'^\[__default__\]\n', '\n', content, flags=re.MULTILINE)

        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(content)

    def write_sorted_config(self, parser, file):
        # Sektionen alphabetisch sortieren
        for section in sorted(parser.sections()):
            file.write(f"[{section}]\n")
            # Schlüssel innerhalb jeder Sektion alphabetisch sortieren
            for key, value in sorted(parser.items(section)):
                file.write(f"{key} = {value}\n")
            file.write("\n")


"""
def read_ini_with_global_section(path, global_section="__global__"):
    self.module.log(f"ForgejoConfig::read_ini_with_global_section({path}, {global_section})")

    with open(path, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    # self.module.log(f"{lines}")

    modified_lines = []
    section_started = False

    for i, line in enumerate(lines):
        stripped = line.strip()
        if not stripped or stripped.startswith(';'):
            modified_lines.append(line)
            continue
        if stripped.startswith('['):
            section_started = True
            break
        else:
            break

    # Nur wenn keine Section direkt am Anfang kommt
    if not section_started:
        modified_lines = [f'[{global_section}]\n'] + lines
    else:
        modified_lines = lines

    # self.module.log(f"{modified_lines}")

    config = ConfigParser()
    config.optionxform = str
    config.read_file(StringIO(''.join(modified_lines)))

    return config

def compare_configs(file1, file2, ignore_map=None):

    changed = False
    config1 = self.read_ini_with_global_section(file1)
    config2 = self.read_ini_with_global_section(file2)

    ignore_map = {k.lower(): [key.lower() for key in v] for k, v in (ignore_map or {}).items()}

    all_sections = set(config1.sections()) | set(config2.sections())

    for section in all_sections:
        self.module.log(f"  - {section}")

        ignore_keys = set(ignore_map.get(section, []))

        if section not in config1:
            self.module.log(f"    - missing in {self.config}")
            checksum1 = ""
        else:
            checksum1 = self.section_checksum(config1, section, ignore_keys)

        if section not in config2:
            self.module.log(f"    - missing in {self.new_config}")
            checksum2 = ""
        else:
            checksum2 = self.section_checksum(config2, section, ignore_keys)

        # if section not in config1 or section not in config2:
        #    continue
        # checksum1 = self.section_checksum(config1, section, ignore_keys)
        # checksum2 = self.section_checksum(config2, section, ignore_keys)

        self.module.log(f"  - '{checksum1}' vs '{checksum2}'")

        if checksum1 != checksum2:
            changed = True
            self.module.log(f"Difference in section [{section}]")
            _added, _removed, _changed = self.diff_section(config1, config2, section)

            if _added or _removed or _changed:
                for k, v in _added:
                    self.module.log(f"  + added  : {k} = {v}")
                for k, v in _removed:
                    self.module.log(f"  - removed: {k} = {v}")
                for k, v1, v2 in _changed:
                    self.module.log(f"  ~ changed: {k} = {v1} → {v2}")

    self.module.log(f"= changed: {changed}")

    return changed

def section_checksum(config, section, ignore_keys=None):
    ignore_keys = ignore_keys or set()
    items = [(k, v) for k, v in config[section].items() if k.lower() not in ignore_keys]
    items.sort()
    concat = ''.join(f'{k}={v}' for k, v in items)

    return hashlib.md5(concat.encode('utf-8')).hexdigest()

def transfer_keys(file1, file2, section_keys_to_transfer, output_file):
    self.module.log(f"ForgejoConfig::transfer_keys({file1}, {file2}, {section_keys_to_transfer}, {output_file})")

    config_ini = self.read_ini_with_global_section(file1)  # .ini
    config_new = self.read_ini_with_global_section(file2)  # .new

    for section, keys in section_keys_to_transfer.items():
        if not config_ini.has_section(section):
            continue

        if not config_new.has_section(section):
            config_new.add_section(section)

        for key in keys:
            if config_ini.has_option(section, key):
                value = config_ini.get(section, key)
                config_new.set(section, key, value)

    # Datei schreiben
    with open(output_file, 'w', encoding='utf-8') as f:
        config_new.write(f)

def diff_section(config1, config2, section, ignore_keys=None):
    ignore_keys = set(ignore_keys or [])
    keys1 = {k: v for k, v in config1.items(section)} if config1.has_section(section) else {}
    keys2 = {k: v for k, v in config2.items(section)} if config2.has_section(section) else {}

    added = []
    removed = []
    changed = []

    for k in keys1:
        if k in ignore_keys:
            continue
        if k not in keys2:
            removed.append((k, keys1[k]))
        elif keys1[k] != keys2[k]:
            changed.append((k, keys1[k], keys2[k]))
    for k in keys2:
        if k in ignore_keys or k in keys1:
            continue
        added.append((k, keys2[k]))

    return added, removed, changed
"""
