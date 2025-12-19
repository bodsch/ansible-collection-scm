# python 3 headers, required if submitting to Ansible

"""
filter plugin file for forgejo runner labels: runner_labels
"""

from __future__ import absolute_import, division, print_function

from ansible.utils.display import Display

__metaclass__ = type

DOCUMENTATION = """
    name: runner_labels
    author: Bodo Schulz (@bodsch)
    version_added: "1.2.0"
    short_description: A filter to create a list for runner labels.
    description:
      - A filter to create a list for runner labels.
    options:
        value:
            description: A dictionary with elements.
            type: dict
            required: True
    notes:
"""

EXAMPLES = r"""
- name: define runner labels
  ansible.builtin.set_fact:
    runnner_labels:
      - label: ubuntu-latest
        type: docker
        container: docker.io/ubuntu:latest
      - label: ubuntu-22.04
        type: docker
        container: docker.io/ubuntu:22.04

- name: create a list for runner labels
  ansible.builtin.debug:
    msg: "{{ runnner_labels | bodsch.scm.runner_labels() }}"
"""

RETURN = """
  _raw:
    description:
      - "A list of consolidated entries"
"""


display = Display()


class FilterModule:
    """ """

    def filters(self):

        return {
            "runner_labels": self.runner_labels,
        }

    def runner_labels(self, data):
        """
        # Labels examples:
        #
        # - node20:docker://node:20-bookworm == node20:docker://docker.io/node:20-bookworm
        #     defines node20 to be the node:20-bookworm image from hub.docker.com
        # - docker:docker://code.forgejo.org/oci/alpine:3.18
        #     defines docker to be the alpine:3.18 image from https://code.forgejo.org/oci/-/packages/container/alpine/3.18

          - ubuntu-latest:docker://docker.io/ubuntu:latest
          - ubuntu-22.04:docker://docker.io/ubuntu:22.04
          - debian-12:docker://bodsch:ansible-debian:12
          ##- 'lxc:lxc://debian:bullseye'
          ##- 'self-hosted:host://-self-hosted'
        """
        display.vv(f"bodsch.scm.runner_labels(self, {data})")

        result = []

        if isinstance(data, list) and len(data) > 0:
            first_value = data[0]
            if isinstance(first_value, dict):
                for label_data in data:
                    _label = []
                    _name = label_data.get("label")
                    _type = label_data.get("type", "docker")
                    _container = label_data.get("container")

                    _label.append(_name)
                    _label.append(_type)
                    _label.append(f"//{_container}")
                    result.append(":".join(_label))
            else:
                result = data

        # display.v(f"= {result}")
        return result
