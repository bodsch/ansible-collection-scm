#!/usr/bin/python3

# (c) 2022-2027, Bodo Schulz <bodo@boone-schulz.de>
# Apache-2.0 (see LICENSE or https://opensource.org/license/apache-2-0)
# SPDX-License-Identifier: Apache-2.0

"""
Ansible filter plugin for selecting database client packages.

Depending on the configured Forgejo database type, this filter
returns only those packages from a given list that are required
for the corresponding database backend (MySQL/MariaDB or PostgreSQL).
"""

from __future__ import annotations

import re
from typing import Any

from ansible.utils.display import Display

DOCUMENTATION = r"""
---
name: forgejo_database_packages
short_description: Select database related packages for the configured Forgejo database type.
version_added: "1.13.0"
author:
  - Bodo Schulz (@bodsch)

description:
  - Returns the subset of a package list that belongs to the given Forgejo database type.
  - For C(mysql) all packages whose name contains C(my) are returned (e.g. C(python3-mysqlclient)).
  - For C(postgres) all packages whose name contains C(pg) are returned (e.g. C(python3-psycopg)).
  - For every other database type (e.g. C(sqlite3)) an empty list is returned.
  - Intended to install only the database client libraries that are actually needed.

positional: _input, packages

options:
  _input:
    description:
      - The Forgejo database type, usually C(forgejo_database.db_type).
      - Only C(mysql) and C(postgres) produce a non-empty result.
    type: str
    required: true

  packages:
    description:
      - List of candidate package names to filter.
      - If omitted or empty, an empty list is returned.
    type: list
    elements: str
    required: false
    default: []
"""

EXAMPLES = r"""
- name: Select database packages for PostgreSQL
  ansible.builtin.set_fact:
    db_packages: >-
      {{
        'postgres'
        | bodsch.scm.forgejo_database_packages(['python3-psycopg', 'python3-mysqlclient'])
      }}

# Result:
# db_packages:
#   - python3-psycopg

- name: Select database packages for MySQL
  ansible.builtin.set_fact:
    db_packages: >-
      {{
        'mysql'
        | bodsch.scm.forgejo_database_packages(['python3-psycopg', 'python3-mysqlclient'])
      }}

# Result:
# db_packages:
#   - python3-mysqlclient

- name: SQLite needs no additional packages
  ansible.builtin.set_fact:
    db_packages: >-
      {{
        'sqlite3'
        | bodsch.scm.forgejo_database_packages(['python3-psycopg', 'python3-mysqlclient'])
      }}

# Result:
# db_packages: []

- name: Install required database packages
  ansible.builtin.package:
    name: >-
      {{
        forgejo_database.db_type | default('sqlite3')
        | bodsch.scm.forgejo_database_packages(forgejo_database_packages)
      }}
    state: present
"""

RETURN = r"""
_value:
  description:
    - Packages matching the given database type.
    - Empty list if the database type is neither C(mysql) nor C(postgres).
  type: list
  elements: str
  sample:
    - python3-psycopg
"""

display = Display()


def forgejo_database_packages(
    data: str,
    packages: list[str] | None = None,
) -> list[str]:
    """
    Return the packages required for the given database type.

    Args:
        data:
            Forgejo database type (``mysql``, ``postgres``, ``sqlite3``, ...).
        packages:
            Candidate package names. ``None`` or an empty list
            results in an empty list.

    Returns:
        Packages matching ``.*my.*`` for ``mysql`` or ``.*pg.*`` for
        ``postgres``; an empty list for every other database type.
    """
    display.vv(
        f"bodsch.scm.forgejo_database_packages(data: {data}, packages: {packages})"
    )

    if not packages:
        return []

    if data in ["mysql", "postgres"]:
        if data == "mysql":
            r = re.compile(".*my.*")
        if data == "postgres":
            r = re.compile(".*pg.*")

        return list(filter(r.match, packages))

    return []


class FilterModule:
    """
    Ansible filter module definition.
    """

    def filters(self) -> dict[str, Any]:
        """
        Return exported Ansible filters.
        """
        return {
            "forgejo_database_packages": forgejo_database_packages,
        }
