#!/usr/bin/python3
# -*- coding: utf-8 -*-

# (c) 2022-2025, Bodo Schulz <bodo@boone-schulz.de>
# Apache-2.0 (see LICENSE or https://opensource.org/license/apache-2-0)
# SPDX-License-Identifier: Apache-2.0

# Type: Ansible Filter
# Collection: bodsch.scm
# File: forgejo_validate_passwords.py
# Directory: plugins/filter

# -------------------------------------------------------------------------------

from __future__ import annotations

from typing import Any, Dict, List, Mapping, Sequence

from ansible.utils.display import Display
from ansible_collections.bodsch.scm.plugins.module_utils.forgejo.password_validator import (
    ForgejoPasswordValidator,
    PasswordPolicy,
)

DOCUMENTATION = r"""
  name: validate_passwords
  short_description: Validate user passwords against a Forgejo password policy.
  version_added: "1.1.0"
  author: Bodo 'bodsch' Schulz <bodo@boone-schulz.de>
  description:
    - Validates passwords for a list of user definitions against a Forgejo
      password policy derived from the C(security) configuration section.
    - Recognized complexity values are C(lower), C(upper), C(digit), and C(spec).
      Any unrecognized values in C(password_complexity) are silently ignored.
    - Returns a failure dict if any user's password violates the policy,
      or a success dict if all passwords pass.
  positional: _input, config
  options:
    _input:
      description:
        - List of user definition dictionaries.
        - Each entry must contain at least C(username) (str) and C(password) (str).
      type: list
      elements: dict
      required: true
    config:
      description:
        - Forgejo C(security) configuration dictionary.
        - Relevant keys are C(password_complexity) (list of str) and
          C(min_password_length) (int, default C(8)).
      type: dict
      required: true
"""

EXAMPLES = r"""
- name: Validate user passwords against Forgejo policy
  ansible.builtin.debug:
    msg: "{{ forgejo_users | bodsch.scm.validate_passwords(forgejo_config.security) }}"

- name: Fail on invalid passwords
  ansible.builtin.fail:
    msg: "Password validation failed: {{ result.result }}"
  vars:
    result: "{{ forgejo_users | bodsch.scm.validate_passwords(forgejo_config.security) }}"
  when: result.failed
"""

RETURN = r"""
  _value:
    description: Validation result dictionary.
    type: dict
    contains:
      failed:
        description: C(true) if at least one password failed validation, C(false) otherwise.
        type: bool
      result:
        description:
          - Only present when C(failed) is C(true).
          - Maps each failing username to a dict with an C(errors) key containing a list
            of violation messages.
        type: dict
"""


display = Display()

_VALID_COMPLEXITY = frozenset(["lower", "upper", "digit", "spec"])


def validate_passwords(
    data: Sequence[Mapping[str, Any]],
    config: Mapping[str, Any],
) -> Dict[str, Any]:
    """
    Validate passwords for user definitions against a Forgejo password policy.

    Args:
        data: List of user dicts, each containing ``username`` and ``password``.
        config: Forgejo security config with ``password_complexity`` and
                ``min_password_length``.

    Returns:
        ``{"failed": True, "result": {username: {"errors": [...]}}}`` on failure,
        ``{"failed": False}`` when all passwords pass.
    """
    display.vv(f"bodsch.scm.validate_passwords(data: {data}, config: {config})")

    raw_complexity: List[str] = config.get("password_complexity", [])
    complexity = [c for c in raw_complexity if c in _VALID_COMPLEXITY]

    display.vv(f"  effective complexity rules: {complexity}")

    policy = PasswordPolicy(
        min_length=config.get("min_password_length", 8),
        complexity=complexity,
    )
    validator = ForgejoPasswordValidator(policy)

    errors: Dict[str, Any] = {}

    for user in data:
        username = str(user.get("username", "<unknown>"))
        password = str(user.get("password", ""))

        display.vv(f"  - validating password for '{username}'")

        validation = validator.validate(password)
        if not validation:
            errors[username] = {"errors": validation.errors}

    if errors:
        return {"failed": True, "result": errors}

    return {"failed": False}


class FilterModule:
    def filters(self) -> Dict[str, Any]:
        return {"validate_passwords": validate_passwords}
