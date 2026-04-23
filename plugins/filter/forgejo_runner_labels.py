#!/usr/bin/python3
# -*- coding: utf-8 -*-

# (c) 2022-2025, Bodo Schulz <bodo@boone-schulz.de>
# Apache-2.0 (see LICENSE or https://opensource.org/license/apache-2-0)
# SPDX-License-Identifier: Apache-2.0

# Type: Ansible Filter
# Collection: bodsch.scm
# File: forgejo_runner_labels.py
# Directory: plugins/filter

# -------------------------------------------------------------------------------

from __future__ import annotations

from typing import Any, Dict, List, Union

from ansible.utils.display import Display

DOCUMENTATION = r"""
  name: runner_labels
  short_description: Build Forgejo runner label strings from a list of label definitions.
  version_added: "1.2.0"
  author: Bodo Schulz (@bodsch)
  description:
    - Converts a list of Forgejo runner label definition dictionaries into the
      colon-separated label strings expected by the Forgejo runner configuration.
    - Each output string follows the format C(<label>:<type>://<container>),
      for example C(ubuntu-latest:docker://docker.io/ubuntu:latest).
    - If the input is already a flat list of strings (not dicts), it is returned
      unchanged to support pass-through usage.
    - Entries missing C(label) or C(container) will produce incomplete strings.
      Ensure all required keys are present in the input data.
  positional: _input
  options:
    _input:
      description:
        - List of runner label definition dictionaries or plain strings.
        - When dicts, each entry should contain C(label) (str), C(container) (str),
          and optionally C(type) (str, default C(docker)).
      type: list
      elements: raw
      required: true
"""

EXAMPLES = r"""
- name: Define runner label configurations
  ansible.builtin.set_fact:
    runner_label_defs:
      - label: ubuntu-latest
        type: docker
        container: docker.io/ubuntu:latest
      - label: ubuntu-22.04
        type: docker
        container: docker.io/ubuntu:22.04
      - label: debian-12
        type: docker
        container: bodsch/ansible-debian:12

- name: Build runner label strings
  ansible.builtin.debug:
    msg: "{{ runner_label_defs | bodsch.scm.runner_labels }}"
  # => [
  #   'ubuntu-latest:docker://docker.io/ubuntu:latest',
  #   'ubuntu-22.04:docker://docker.io/ubuntu:22.04',
  #   'debian-12:docker://bodsch/ansible-debian:12',
  # ]

- name: Pass-through if already a list of strings
  ansible.builtin.debug:
    msg: "{{ ['ubuntu-latest:docker://docker.io/ubuntu:latest'] | bodsch.scm.runner_labels }}"
  # => ['ubuntu-latest:docker://docker.io/ubuntu:latest']
"""

RETURN = r"""
  _value:
    description:
      - List of runner label strings in the format C(<label>:<type>://<container>).
      - Returned unchanged if the input is already a list of strings.
    type: list
    elements: str
"""

display = Display()


def runner_labels(data: List[Union[Dict[str, Any], str]]) -> List[str]:
    """
    Build Forgejo runner label strings from a list of label definition dicts.

    Each dict is converted to ``<label>:<type>://<container>``.
    A flat list of strings is returned unchanged (pass-through).

    Args:
        data: List of label definition dicts or plain label strings.

    Returns:
        List of formatted runner label strings.
    """
    display.vv(f"bodsch.scm.runner_labels(data: {data})")

    if not data:
        return []

    # Pass-through: input is already a list of strings
    if not isinstance(data[0], dict):
        return data  # type: ignore[return-value]

    result: List[str] = []
    for entry in data:
        label = entry.get("label")
        type_ = entry.get("type", "docker")
        container = entry.get("container")
        result.append(f"{label}:{type_}://{container}")

    display.vv(f"  = {result}")

    return result


class FilterModule:
    def filters(self) -> Dict[str, Any]:
        return {"runner_labels": runner_labels}
