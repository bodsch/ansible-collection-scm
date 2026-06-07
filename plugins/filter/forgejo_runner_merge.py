#!/usr/bin/python3
# -*- coding: utf-8 -*-

# (c) 2022-2025, Bodo Schulz <bodo@boone-schulz.de>
# Apache-2.0 (see LICENSE or https://opensource.org/license/apache-2-0)
# SPDX-License-Identifier: Apache-2.0

# Type: Ansible Filter
# Collection: bodsch.scm
# File: forgejo_runner_merge.py
# Directory: plugins/filter

# -------------------------------------------------------------------------------

from __future__ import annotations

from typing import Any, Dict, List

from ansible.utils.display import Display

DOCUMENTATION = r"""
  name: add_runner_uuid
  short_description: Validate that all runner registration secrets are valid 40-character hex tokens.
  version_added: "1.2.0"
  author: Bodo Schulz (@bodsch)
  description: TBD
"""

EXAMPLES = r"""

"""

RETURN = r"""

"""

display = Display()


def add_runner_uuid(
    data: List[Dict[str, Any]], forgejo_runners: List[Dict[str, Any]]
) -> bool:
    """
    Validate that all runner registration secrets are valid 40-char hex tokens.

    Args:
        data: List of registrated Runners  with uuid
        forgejo_runners: List of runner registration dicts, each containing a ``secret`` key.

    Returns:
        True if every secret is a valid 40-character hex string, False otherwise.
    """
    display.vv(
        f"bodsch.scm.add_runner_uuid(data: {data}, forgejo_runners: {forgejo_runners})"
    )

    _merged = merge_by_key(right=forgejo_runners, left=data)

    if not data:
        return False

    display.vv(f" _merged: {_merged}")

    return _merged


def merge_by_key(
    left: list[dict[str, Any]],
    right: list[dict[str, Any]],
    key: str = "name",
) -> list[dict[str, Any]]:
    """
    Merge two lists of dictionaries by a shared identifier key.

    Entries from ``right`` take precedence over entries from ``left`` when the
    same dictionary key is present in both. Items that exist in only one of the
    lists are kept untouched. The original ordering of ``left`` is preserved;
    items that exist only in ``right`` are appended afterwards in their
    original order. The merge is shallow — nested structures are not merged
    recursively but replaced as a whole.

    :param left: Base list of dictionaries.
    :param right: Leading list of dictionaries; its values win on conflicts.
    :param key: Dictionary key used to match entries between both lists.
    :return: A new list containing merged dictionaries. Inputs are not mutated.
    :raises KeyError: If any dictionary in either list lacks ``key``.
    """
    right_index: dict[Any, dict[str, Any]] = {item[key]: item for item in right}
    seen: set[Any] = set()
    merged: list[dict[str, Any]] = []

    for item in left:
        identifier = item[key]
        seen.add(identifier)
        # right wins because it is unpacked last
        merged.append({**item, **right_index.get(identifier, {})})

    for item in right:
        if item[key] not in seen:
            merged.append(dict(item))

    return merged


class FilterModule:
    def filters(self) -> Dict[str, Any]:
        return {"add_runner_uuid": add_runner_uuid}
