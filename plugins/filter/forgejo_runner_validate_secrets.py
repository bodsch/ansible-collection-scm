#!/usr/bin/python3
# -*- coding: utf-8 -*-

# (c) 2022-2025, Bodo Schulz <bodo@boone-schulz.de>
# Apache-2.0 (see LICENSE or https://opensource.org/license/apache-2-0)
# SPDX-License-Identifier: Apache-2.0

# Type: Ansible Filter
# Collection: bodsch.scm
# File: forgejo_runner_validate_secrets.py
# Directory: plugins/filter

# -------------------------------------------------------------------------------

from __future__ import annotations

import re
from typing import Any, Dict, List, Union

from ansible.utils.display import Display

DOCUMENTATION = r"""
  name: validate_runner_secrets
  short_description: Validate that all runner registration secrets are valid 40-character hex tokens.
  version_added: "1.2.0"
  author: Bodo Schulz (@bodsch)
  description:
    - Iterates over a list of Forgejo runner registration dictionaries and checks
      whether every C(secret) value is a valid 40-character hexadecimal token
      (characters C(0-9) and C(a-f), case-insensitive).
    - A single dictionary (e.g. the C(cache) section of C(forgejo_runner_config))
      or a plain secret string is treated as a list with one entry.
    - Returns C(true) only if B(all) entries pass validation.
    - Returns C(false) if any entry has a missing, empty, or malformed secret,
      or if the input list is empty.
  positional: _input
  options:
    _input:
      description:
        - List of runner registration dictionaries, a single dictionary or a secret string.
        - Each dictionary must contain a C(secret) key with the token as a string.
      type: raw
      required: true
    allow_empty:
      description:
        - Treat a missing or empty secret as valid.
        - Useful for the cache secret, which the runner generates itself when it is empty.
      type: bool
      default: false
"""

EXAMPLES = r"""
- name: Validate all runner secrets
  ansible.builtin.set_fact:
    _secrets_valid: "{{ forgejo_runner_register | default([]) | bodsch.scm.validate_runner_secrets }}"

- name: Abort if any secret is invalid
  ansible.builtin.fail:
    msg: "One or more runner secrets are not valid 40-character hex tokens."
  when: not _secrets_valid

- name: Validate the cache secret (empty is allowed)
  ansible.builtin.set_fact:
    _cache_secret_valid: "{{ forgejo_runner_config.cache | bodsch.scm.validate_runner_secrets(allow_empty=true) }}"

# Input example:
# forgejo_runner_register:
#   - name: instance
#     instance: http://forgejo.example.com:3000
#     secret: 4ef3eb262c04aad5e279511c1c86f7377e28d6b9
#     scope: ''
#     labels:
#       - self-hosted
# => true

# Malformed secret:
# secret: "tooshort"
# => false
"""

RETURN = r"""
  _value:
    description:
      - C(true) if every entry's secret is a valid 40-character hexadecimal token.
      - C(false) if any entry fails validation or the input list is empty.
    type: bool
"""

display = Display()

_SECRET_RE = re.compile(r"^[0-9a-f]{40}$", re.IGNORECASE)


def _is_valid_secret(secret: Any, allow_empty: bool) -> bool:
    """
    Check a single secret value.

    Args:
        secret: The secret to check.
        allow_empty: Treat ``None`` or an empty string as valid.

    Returns:
        True if the secret is a valid 40-character hex string (or empty and allowed).
    """
    if secret is None or (isinstance(secret, str) and not secret.strip()):
        return allow_empty

    return isinstance(secret, str) and _SECRET_RE.fullmatch(secret.strip()) is not None


def validate_runner_secrets(
    data: Union[List[Dict[str, Any]], Dict[str, Any], str],
    allow_empty: bool = False,
) -> bool:
    """
    Validate that all runner secrets are valid 40-char hex tokens.

    Args:
        data: List of dicts containing a ``secret`` key, a single dict or a secret string.
        allow_empty: Treat a missing or empty secret as valid.

    Returns:
        True if every secret is a valid 40-character hex string, False otherwise.
    """
    display.vv(f"bodsch.scm.validate_runner_secrets(data: {data}, allow_empty: {allow_empty})")

    if isinstance(data, (str, dict)):
        data = [data]

    if not data:
        return False

    return all(
        _is_valid_secret(
            entry.get("secret") if isinstance(entry, dict) else entry,
            allow_empty,
        )
        for entry in data
    )


class FilterModule:
    def filters(self) -> Dict[str, Any]:
        return {"validate_runner_secrets": validate_runner_secrets}
