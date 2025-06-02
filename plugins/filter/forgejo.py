# python 3 headers, required if submitting to Ansible

from __future__ import (absolute_import, division, print_function)
from ansible.utils.display import Display

__metaclass__ = type

display = Display()


class FilterModule():
    """
    """

    def filters(self):

        return {
            'sub_logger': self.sub_logger,
            'sub_logger_data': self.sub_logger_data,
        }

    def sub_logger(self, data):
        """
            ;logger.access.MODE=
            ;logger.router.MODE=,
            ;logger.xorm.MODE=,
        """
        display.v(f"sub_logger(self, {data})")

        return [x.get("name") for x in data if x.get("mode", None)]

    def sub_logger_data(self, data, logger):
        """
        """
        display.v(f"sub_logger_data(self, {data}, {logger})")

        result = [x for x in data if x.get("name", None) == logger]

        # TODO
        # validate keys (and values)?
        if len(result) == 1:
            return result[0]

        return result
