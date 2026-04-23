#!/usr/bin/python3
# -*- coding: utf-8 -*-

# (c) 2022-2025, Bodo Schulz <bodo@boone-schulz.de>
# Apache-2.0 (see LICENSE or https://opensource.org/license/apache-2-0)
# SPDX-License-Identifier: Apache-2.0

# Type: Ansible Filter
# Collection: bodsch.scm
# File: forgejo_sub_logger_data.py
# Directory: plugins/filter

# -------------------------------------------------------------------------------

from __future__ import annotations

from typing import Any, Dict, List, Union

from ansible.utils.display import Display

DOCUMENTATION = r"""
  name: sub_logger_data
  short_description: Retrieve a Forgejo logger configuration by name.
  version_added: "1.0.0"
  author: Bodo 'bodsch' Schulz <bodo@boone-schulz.de>
  description:
    - Searches a list of Forgejo sub-logger configuration dictionaries for an
      entry whose C(name) matches the given C(logger) argument.
    - If exactly one match is found, the dict is returned directly (unwrapped).
    - If zero or more than one match is found, the raw list is returned.
      Multiple matches indicate a misconfiguration and should be treated as an
      error in the calling task.
  positional: _input, logger
  options:
    _input:
      description:
        - List of logger configuration dictionaries.
        - Each entry should contain at least C(name) (str) and C(mode) (str).
      type: list
      elements: dict
      required: true
    logger:
      description:
        - The logger name to look up (e.g. C(console), C(file), C(file-error)).
      type: str
      required: true
"""

EXAMPLES = r"""
- name: Get configuration for the console logger
  ansible.builtin.debug:
    msg: "{{ forgejo_loggers | bodsch.scm.sub_logger_data('console') }}"
  vars:
    forgejo_loggers:
      - name: console
        mode: console
        level: Info
        flags: stdflags
        colorize: false
      - name: file
        mode: file
        level: Info
        file_name: forgejo.log
  # => {'name': 'console', 'mode': 'console', 'level': 'Info', 'flags': 'stdflags', 'colorize': false}

- name: Get configuration for the file logger
  ansible.builtin.debug:
    msg: "{{ forgejo_loggers | bodsch.scm.sub_logger_data('file') }}"
  # => {'name': 'file', 'mode': 'file', 'level': 'Info', 'file_name': 'forgejo.log'}

- name: Handle missing logger gracefully
  ansible.builtin.debug:
    msg: "{{ forgejo_loggers | bodsch.scm.sub_logger_data('nonexistent') }}"
  # => []
"""

RETURN = r"""
  _value:
    description:
      - The matching logger configuration dictionary if exactly one match was found.
      - The raw list of matches (empty or multiple) otherwise.
    type: raw
"""


display = Display()


def sub_logger_data(
    data: List[Dict[str, Any]], logger: str
) -> Union[Dict[str, Any], List[Dict[str, Any]]]:
    """
    Retrieve a Forgejo logger configuration dict by name.

    Args:
        data:   List of logger configuration dicts.
        logger: The logger name to search for.

    Returns:
        The single matching dict if exactly one result is found,
        otherwise the raw list (empty list or list with multiple matches).
    """
    display.vv(f"bodsch.scm.sub_logger_data(data: {data}, logger: {logger})")

    result = [entry for entry in data if entry.get("name") == logger]

    display.vv(f"  = {result}")

    if len(result) == 1:
        return result[0]

    return result


class FilterModule:
    def filters(self) -> Dict[str, Any]:
        return {"sub_logger_data": sub_logger_data}
