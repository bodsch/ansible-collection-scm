# python 3 headers, required if submitting to Ansible

from __future__ import (absolute_import, division, print_function)
__metaclass__ = type

from ansible.utils.display import Display

display = Display()


class FilterModule():
    """
    """
    def filters(self):

        return {
            'runner_labels': self.runner_labels,
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
        # display.v(f"runner_labels(self, {data})")
        result = []

        if isinstance(data, list):
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
