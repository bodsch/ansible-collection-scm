#!/usr/bin/python3
# -*- coding: utf-8 -*-

# (c) 2022-2025, Bodo Schulz <bodo@boone-schulz.de>
# Apache-2.0 (see LICENSE or https://opensource.org/license/apache-2-0)
# SPDX-License-Identifier: Apache-2.0

# Type: Ansible Filter
# Collection: bodsch.scm
# File: forgej_sub_logger.py
# Directory: plugins/filter

# -------------------------------------------------------------------------------

from __future__ import annotations

from typing import Any, Dict, List

from ansible.utils.display import Display

DOCUMENTATION = r"""
  name: sub_logger
  short_description: Extract logger names from a list of Forgejo logger definitions.
  version_added: "1.0.0"
  author: Bodo 'bodsch' Schulz <bodo@boone-schulz.de>
  description:
    - Returns a list of logger names from a list of Forgejo sub-logger
      configuration dictionaries.
    - Only entries that have a C(mode) key set are included.
    - The result is suitable for use in Forgejo INI config keys such as
      C(logger.access.MODE), C(logger.router.MODE), or C(logger.xorm.MODE).
  positional: _input
  options:
    _input:
      description:
        - List of logger configuration dictionaries.
        - Each entry should contain at least C(name) (str) and C(mode) (str).
      type: list
      elements: dict
      required: true
"""

EXAMPLES = r"""
- name: Get all active logger names
  ansible.builtin.debug:
    msg: "{{ forgejo_loggers | bodsch.scm.sub_logger }}"
  vars:
    forgejo_loggers:
      - name: console
        mode: console
        level: Info
      - name: file
        mode: file
        level: Info
        file_name: forgejo.log
      - name: file-error
        mode: file
        level: Error
        file_name: forgejo.err
  # => ['console', 'file', 'file-error']

- name: Use result in INI template
  ansible.builtin.template:
    src: forgejo.ini.j2
    dest: /etc/forgejo/app.ini
  vars:
    active_loggers: "{{ forgejo_loggers | bodsch.scm.sub_logger | join(',') }}"
  # Produces: logger.access.MODE=console,file,file-error
"""

RETURN = r"""
  _value:
    description: List of logger name strings for entries that have a C(mode) set.
    type: list
    elements: str
"""


display = Display()


def sub_logger(data: List[Dict[str, Any]]) -> List[str]:
    """
    Extract logger names from a list of Forgejo logger definitions.

    Only entries with a non-empty ``mode`` key are included.

    Args:
        data: List of logger configuration dicts.

    Returns:
        List of logger name strings.
    """
    display.vv(f"bodsch.scm.sub_logger(data: {data})")

    result = [entry.get("name") for entry in data if entry.get("mode")]

    display.vv(f"  = {result}")

    return result


class FilterModule:
    def filters(self) -> Dict[str, Any]:
        return {"sub_logger": sub_logger}
