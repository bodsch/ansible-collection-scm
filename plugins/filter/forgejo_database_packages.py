#!/usr/bin/python3

# (c) 2022-2027, Bodo Schulz <bodo@boone-schulz.de>
# Apache-2.0 (see LICENSE or https://opensource.org/license/apache-2-0)
# SPDX-License-Identifier: Apache-2.0

"""
Ansible filter plugin for ... TBD
"""

from __future__ import annotations

import re
from typing import Any

from ansible.utils.display import Display

display = Display()


def forgejo_database_packages(
    data: str,
    packages: list[str] | None = None,
) -> list[str]:
    """ """
    display.vv(
        f"bodsch.scm.forgejo_database_packages(data: {data}, packages: {packages})"
    )

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
