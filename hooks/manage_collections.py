#!/usr/bin/python3
# -*- coding: utf-8 -*-

# (c) 2022-2024, Bodo Schulz <bodo@boone-schulz.de>

import os
import yaml
import json
import subprocess

import logging

# from pathlib import Path
from packaging.version import Version, InvalidVersion
from packaging.specifiers import SpecifierSet, InvalidSpecifier
from typing import List
import site

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

VERSION = "2.0.1"


class AnsibleCollectionManager():

    def __init__(self, directory: str = None):
        """
        """
        self.tox_silence = os.environ.get('TOX_SILENCE', "true").lower() in ("1", "true", "yes", "on")

        self.requirements_file = "collections.yml"

        if directory:
            os.chdir(directory)

    def run(self, required: List[dict] = None):
        """
        """
        required.sort(key=lambda x: x['name'])
        unique = []
        seen = set()
        for item in required:
            if item['name'] not in seen:
                unique.append(item)
                seen.add(item['name'])

        required = unique

        installed = self.get_installed_collections()

        for item in required:
            name = item.get("name")
            required_version = item.get("version")
            current_version = installed.get(name)

            if current_version:
                if required_version:
                    if not self.is_version_compatible(current_version, required_version):
                        logging.info(
                            f"🔄 '{name}' is installed in version {current_version}, {required_version} is required.")
                        self.install_collection(name)
                    else:
                        logging.info(
                            f"✅ '{name}' is installed in compatible version {current_version}.")
                else:
                    logging.info(
                        f"✅ '{name}' is installed in version {current_version}.")
            else:
                logging.info(f"❌ '{name}' is not installed.")
                self.install_collection(name)

        print("")

    def load_required_collections(self, path="collections.yml"):
        """
            Lädt die benötigten Collections aus der YAML-Datei.
        """
        # logging.debug(f"AnsibleCollectionManager::load_required_collections({path})")
        result = []

        with open(path, "r") as f:
            data = yaml.safe_load(f)
            if data and isinstance(data, dict):
                result = data.get("collections", [])

        return result

    def load_collection_dependencies(self, path="galaxy.yml"):
        """
        """
        with open(path, "r") as f:
            data = yaml.safe_load(f)
            if data and isinstance(data, dict):
                r = data.get("dependencies", [])
                result = [{"name": k, "version": v} if v is not None and v !=
                          "*" else {"name": k} for k, v in r.items()]

        return result

    def is_version_compatible(self, installed_version: str, required_spec: str) -> bool:
        """
            Prüft, ob die installierte Version mit dem geforderten Version-String kompatibel ist.
        """
        try:
            return Version(installed_version) in SpecifierSet(required_spec)
        except InvalidVersion:
            logging.warning(
                f"⚠️ Ungültige installierte Version: {installed_version}")
            return False
        except InvalidSpecifier:
            logging.error(
                f"❌ Ungültiger Versions-Spezifizierer: '{required_spec}' — bitte verwende z. B. '>=4.0'")
            return False

    def get_ansible_collections_paths(self, ):
        """
            Ermittelt gültige Ansible-Collection-Verzeichnisse anhand von Umgebungsvariablen
            oder Standards.
        """
        paths = []
        env_paths = os.environ.get("ANSIBLE_COLLECTIONS_PATHS")

        if env_paths:
            paths.extend([os.path.join(p, "ansible_collections")
                         for p in env_paths.split(os.pathsep)])
        else:
            # Standard: ~/.ansible/collections/ansible_collections
            paths.append(os.path.join(os.path.expanduser("~"),
                         ".ansible", "collections", "ansible_collections"))

            # Dynamisch ermitteln: site-packages
            for sp in site.getsitepackages():
                paths.append(os.path.join(sp, "ansible_collections"))

        return paths

    def get_installed_collections(self, ):
        """
            Durchsucht bekannte Collection-Pfade nach installierten Collections und ermittelt deren Versionen.
        """
        installed = {}

        for base_path in self.get_ansible_collections_paths():
            if not os.path.isdir(base_path):
                continue

            for namespace in os.listdir(base_path):
                ns_path = os.path.join(base_path, namespace)
                if not os.path.isdir(ns_path):
                    continue

                for collection in os.listdir(ns_path):
                    coll_path = os.path.join(ns_path, collection)
                    manifest = os.path.join(coll_path, "MANIFEST.json")
                    if os.path.isfile(manifest):
                        try:
                            with open(manifest) as f:
                                data = json.load(f)
                                name = f"{namespace}.{collection}"
                                info = data.get("collection_info", {})
                                version = info.get("version")
                                namespace = info.get("namespace")
                                name = info.get("name")

                                if namespace and name and version:
                                    full_name = f"{namespace}.{name}"
                                    # logging.debug(f"🔍 Found '{full_name}' version {version} at {coll_path}")
                                    if full_name not in installed:
                                        installed[full_name] = version
                                    else:
                                        try:
                                            if Version(version) > Version(installed[full_name]):
                                                installed[full_name] = version
                                        except InvalidVersion:
                                            pass  # falls Versionsvergleich fehlschlägt: einfach ignorieren

                        except Exception as e:
                            logging.error(
                                f"⚠️ Errors when reading {manifest}: {e}")

        return installed

    def install_collection(self, name):
        """
            Installiert eine Collection über ansible-galaxy (ohne Versionsparameter).
        """
        logging.info(f"📦 Install ansible-galaxy collection {name} ...")

        cmd = [
            "ansible-galaxy",
            "collection",
            "install",
            "--force",
            name
        ]

        try:
            subprocess.run(
                cmd,
                capture_output=self.tox_silence,
                text=True,
                check=True
            )
        except subprocess.CalledProcessError as e:
            """
            """
            cmd_str = ' '.join(cmd)
            logging.error("Command:")
            logging.error(f"  {cmd_str}")
            print("")
            logging.error('   STDOUT:')
            if e.stdout:
                logging.error(f"  {e.stdout.strip()}")
            print("")
            logging.error('   STDERR:')
            if e.stderr:
                logging.error(f"  {e.stderr.strip()}")
            print("")

            # sys.exit(1)
