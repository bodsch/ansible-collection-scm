#!/usr/bin/python3
# -*- coding: utf-8 -*-

from __future__ import absolute_import, print_function
import urllib3
import requests
import json
import os
import re
from enum import Enum
import datetime

from packaging.version import parse as parseVersion
from pathlib import Path

from ansible.module_utils.basic import AnsibleModule

__metaclass__ = type

ANSIBLE_METADATA = {
    'metadata_version': '0.1',
    'status': ['preview'],
    'supported_by': 'community'
}

DOCUMENTATION = r'''
---
module: urbanterror_api

short_description: ""

description: ""

version_added: "0.1.0"
author: "..."
options:

'''

EXAMPLES = r"""

"""

RETURN = r"""


"""

class Architecture(Enum):
    amd64   = "x86_64"
    arm64   = "aarch64"
    armv7   = "armv7l"
    armv6   = "armv6l"

class GithubChecksum(object):
    """
    Main Class
    """
    module = None

    def __init__(self, module):
        """
          Initialize all needed Variables
        """
        self.module = module

        self.project = module.params.get("project")
        self.repository = module.params.get("repository")
        self.github_username = module.params.get("user")
        self.github_password = module.params.get("password")
        self.architecture = Architecture(module.params.get("architecture")).name
        self.system = module.params.get("system").lower()
        self.checksum_file = module.params.get("checksum_file")
        self.version = module.params.get("version")
        self.cache_minutes = int(module.params.get("cache"))

        # https://github.com/prometheus/alertmanager/releases/download/v0.25.0/sha256sums.txt
        self.github_url = f"https://github.com/{self.project}/{self.repository}/releases/download"

        self.cache_directory = f"{Path.home()}/.ansible/cache/github/{self.project}/{self.repository}"
        self.cache_file_name = os.path.join(self.cache_directory, f"{self.version}_{self.checksum_file}")

        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

    def run(self):
        """
        """
        checksum = None
        rc = 10

        self.__create_directory(self.cache_directory)
        data = self.latest_information()

        # self.module.log(msg=f"data: {data} {type(data)}")
        # self.module.log(msg=f"  - {self.repository}")
        # self.module.log(msg=f"  - {self.system}")
        # self.module.log(msg=f"  - {self.architecture}")

        # e9fa07f094b8efa3f1f209dc7d51a7cf428574906c7fd8eac9a3aed08b03ed63  alertmanager-0.25.0.darwin-amd64.tar.gz
        checksum = [x for x in data if re.search(fr".*{self.repository}.*{self.system}.*{self.architecture}.*", x)]

        if isinstance(checksum, list) and len(checksum):
            checksum = checksum[0]

        if isinstance(checksum, str):
            checksum = checksum.split(" ")[0]

        self.module.log(msg=f"checksum: {checksum}")

        if len(checksum) > 0:
            rc = 0

        return dict(
            failed = False,
            rc = rc,
            checksum = checksum,
            checksums = data
        )

    def latest_information(self):
        """
        """
        output = None

        if os.path.exists(self.cache_file_name):
            self.module.log(msg=f" - read cache file  {self.cache_file_name}")

            now           = datetime.datetime.now()
            creation_time = datetime.datetime.fromtimestamp(os.path.getctime(self.cache_file_name))
            diff          = now - creation_time
            # define the difference from now to the creation time in minutes
            cached_time   = diff.total_seconds() / 60
            out_of_cache  = cached_time > self.cache_minutes

            # self.module.log(msg=f" - now            {now}")
            # self.module.log(msg=f" - creation_time  {creation_time}")
            # self.module.log(msg=f" - cached since   {cached_time}")
            # self.module.log(msg=f" - out of cache   {out_of_cache}")

            if out_of_cache:
                os.remove(self.cache_file_name)
            else:
                with open(self.cache_file_name, "r") as f:
                    output = json.loads(f.read())

                    return output

        if not output:
            self.module.log(msg=f" - read from url  {self.github_url}")

            status_code, output = self.__call_url()

            # self.module.log(msg=f" - output  {output} {type(output)}")
            # convert the strings into a list
            output = output.split("\n")
            # and remove empty elements
            output[:] = [x for x in output if x]

            self.module.log(msg=f" - output  {output} {type(output)}")

            if status_code == 200:
                self.save_latest_information(output)

                return output

    def save_latest_information(self, data):
        """
        """
        with open(self.cache_file_name, "w") as f:
            json.dump(data, f, indent=2, sort_keys=True)

    def __create_directory(self, dir):
        """
        """
        try:
            os.makedirs(dir, exist_ok=True)
        except FileExistsError:
            pass

        if os.path.isdir(dir):
            return True
        else:
            return False

    def __call_url(self, method='GET', data=None):
        """
        """
        response = None

        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json;charset=utf-8"
        }

        github_url = f"{self.github_url}/v{self.version}/{self.checksum_file}"

        try:
            authentication = (self.github_username, self.github_password)

            if method == "GET":
                response = requests.get(
                    github_url,
                    headers=headers,
                    auth=authentication
                )

            else:
                print("unsupported")
                pass

            response.raise_for_status()

            self.module.log(msg=f" text    : {response.text} / {type(response.text)}")
            # self.module.log(msg=f" json    : {response.json()} / {type(response.json())}")
            self.module.log(msg=f" headers : {response.headers}")
            self.module.log(msg=f" code    : {response.status_code}")
            self.module.log(msg="------------------------------------------------------------------")

            return response.status_code, response.text

        except requests.exceptions.HTTPError as e:
            self.module.log(msg=f"ERROR   : {e}")

            status_code = e.response.status_code
            status_message = e.response.text
            # self.module.log(msg=f" status_message : {status_message} / {type(status_message)}")
            # self.module.log(msg=f" status_message : {e.response.json()}")

            return status_code, status_message

        except ConnectionError as e:
            error_text = f"{type(e).__name__} {(str(e) if len(e.args) == 0 else str(e.args[0]))}"
            self.module.log(msg=f"ERROR   : {error_text}")

            self.module.log(msg="------------------------------------------------------------------")
            return 500, error_text

        except Exception as e:
            self.module.log(msg=f"ERROR   : {e}")
            # self.module.log(msg=f" text    : {response.text} / {type(response.text)}")
            # self.module.log(msg=f" json    : {response.json()} / {type(response.json())}")
            # self.module.log(msg=f" headers : {response.headers}")
            # self.module.log(msg=f" code    : {response.status_code}")
            # self.module.log(msg="------------------------------------------------------------------")

            return response.status_code, response.text

    def version_sort(self, version_list):
        """
        """
        version_list.sort(key = parseVersion)

        return version_list


def main():
    """
    """
    argument_spec=dict(
        project=dict(
            type=str,
            required=True,
        ),
        repository=dict(
            type=str,
            required=True,
        ),
        architecture=dict(
            type=str,
            required=False,
            default="x86_64",
        ),
        system=dict(
            type=str,
            required=False,
            default="Linux",
        ),
        checksum_file=dict(
            type=str,
            required=False,
            default="checksums.txt",
        ),
        user=dict(
            type=str,
            required=False,
        ),
        password=dict(
            type=str,
            required=False,
            no_log=True
        ),
        version=dict(
            type=str,
            required=True,
        ),
        cache=dict(
            type=int,
            required=False,
            default=60
        )
    )

    module = AnsibleModule(
        argument_spec = argument_spec,
        supports_check_mode = False,
    )

    api = GithubChecksum(module)
    result = api.run()

    module.log(msg=f"= result : {result}")

    module.exit_json(**result)


# import module snippets
if __name__ == '__main__':
    main()
