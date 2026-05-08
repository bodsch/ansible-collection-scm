#!/usr/bin/python3
# -*- coding: utf-8 -*-

# (c) 2022-2026, Bodo Schulz <bodo@boone-schulz.de>
# Apache-2.0 (see LICENSE or https://opensource.org/license/apache-2-0)
# SPDX-License-Identifier: Apache-2.0

"""
Ansible filter plugin for building normalized Unix group lists.

This filter combines a primary group with additional groups,
removes duplicates, filters invalid values, and returns
a sorted deterministic list.
"""

from __future__ import annotations

from typing import Any

from ansible.errors import AnsibleFilterError
from ansible.utils.display import Display

DOCUMENTATION = r"""
---
name: runner_groups
short_description: Build a normalized Unix group list for Forgejo runner users.
version_added: "1.9.2"
author:
  - Bodo Schulz (@bodsch)

description:
  - Combines a primary Unix group with additional group names.
  - Removes duplicate entries.
  - Filters empty values.
  - Returns a deterministic sorted list.
  - Intended for usage with C(ansible.builtin.user).

positional: _input

options:
  _input:
    description:
      - Primary Unix group name.
    type: str
    required: true

  additional_groups:
    description:
      - Additional Unix groups.
      - Duplicate and empty entries are removed automatically.
    type: list
    elements: str
    required: false
"""

EXAMPLES = r"""
- name: Build Forgejo runner groups
  ansible.builtin.set_fact:
    forgejo_groups: >-
      {{
        'forgejo'
        | bodsch.scm.runner_groups(['docker', 'audio', 'docker'])
      }}

- name: Show result
  ansible.builtin.debug:
    var: forgejo_groups

# Result:
# forgejo_groups:
#   - audio
#   - docker
#   - forgejo

- name: Use with ansible.builtin.user
  ansible.builtin.user:
    name: forgejo
    groups: >-
      {{
        'forgejo'
        | bodsch.scm.runner_groups(['docker'])
      }}
"""

RETURN = r"""
_value:
  description:
    - Normalized Unix group list.
  type: list
  elements: str
  sample:
    - docker
    - forgejo
"""

display = Display()


class RunnerGroupBuilder:
    """
    Internal helper class for building normalized Unix group lists.
    """

    @staticmethod
    def build(primary_group: str, additional_groups: list[str] | None = None) -> list[str]:
        """
        Build a normalized and deterministic group list.

        Args:
            primary_group:
                Primary Unix group name.

            additional_groups:
                Optional list of additional Unix groups.

        Returns:
            Sorted list of unique Unix group names.

        Raises:
            AnsibleFilterError:
                Raised when invalid input types are provided.
        """
        if not isinstance(primary_group, str):
            raise AnsibleFilterError(
                f"'primary_group' must be of type str, got {type(primary_group).__name__}"
            )

        primary_group = primary_group.strip()

        if not primary_group:
            raise AnsibleFilterError("'primary_group' must not be empty")

        if additional_groups is None:
            additional_groups = []

        if not isinstance(additional_groups, list):
            raise AnsibleFilterError(
                f"'additional_groups' must be of type list, got {type(additional_groups).__name__}"
            )

        normalized_groups: set[str] = {
            group.strip()
            for group in additional_groups
            if isinstance(group, str) and group.strip()
        }

        normalized_groups.add(primary_group)

        result = sorted(normalized_groups)

        display.vv(
            "bodsch.scm.runner_groups("
            f"primary_group={primary_group}, "
            f"additional_groups={additional_groups}"
            f") -> {result}"
        )

        return result


def runner_groups(
    primary_group: str,
    additional_groups: list[str] | None = None,
) -> list[str]:
    """
    Public Ansible filter API.

    Args:
        primary_group:
            Primary Unix group name.

        additional_groups:
            Optional list of additional Unix groups.

    Returns:
        Sorted list of unique Unix group names.
    """
    return RunnerGroupBuilder.build(primary_group, additional_groups)


class FilterModule:
    """
    Ansible filter module definition.
    """

    def filters(self) -> dict[str, Any]:
        """
        Return exported Ansible filters.
        """
        return {
            "runner_groups": runner_groups,
        }
