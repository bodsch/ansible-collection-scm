#!/usr/bin/python3
# -*- coding: utf-8 -*-

# (c) 2024-2025, Bodo Schulz <bodo@boone-schulz.de>
# Apache (see LICENSE or https://opensource.org/licenses/Apache-2.0)

from __future__ import absolute_import, division, print_function

import os

import git
from ansible.module_utils.basic import AnsibleModule

DOCUMENTATION = r"""
---
module: git_info
author: Bodo 'bodsch' Schulz <bodo@boone-schulz.de>
version_added: 1.3.0

short_description: Organise various information from a git repository.
description:
  - This module retrieves various details from a Git repository such as the current branch, commit IDs, last commit date, and latest tag.
  - It can be useful for deployment scripts or validation tasks where Git metadata is needed.

options:
  work_dir:
    description:
      - Directory from which the Git information is to be retrieved.
      - This directory must contain a valid Git repository or be a subdirectory of one.
    required: true
    type: path
"""

EXAMPLES = r"""
- name: Obtain git information from download path
  become: true
  bodsch.scm.git_info:
    work_dir: "{{ repository_tmp_directory }}"
  register: _repository_information

- name: Obtain git information from install path
  become: true
  bodsch.scm.git_info:
    work_dir: "{{ repository_install_path }}/active"
  register: _installed_information

- name: Show extracted git info
  debug:
    var: _installed_information.git
"""

RETURN = r"""
git:
  description:
    - Dictionary containing Git repository information.
  returned: success
  type: dict
  contains:
    version:
      description:
        - A calculated version based on the branch.
        - If the branch is master or main, the latest tag is used.
        - Otherwise, the short commit ID is used.
      type: string
      sample: "v1.2.3"
    branch:
      description:
        - The current branch name or 'detached' if in detached HEAD state.
      type: string
      sample: "main"
    latest_tag:
      description:
        - The latest git tag in the repository.
      type: string
      sample: "v1.2.3"
    commit_id:
      description:
        - Full commit SHA of the current branch.
      type: string
      sample: "9fceb02c5a0d3e6a..."
    last_commit_id:
      description:
        - SHA of the last commit in the repository (from iter_commits).
      type: string
      sample: "1a2b3c4d5e6f7g8h..."
    commit_short_id:
      description:
        - Short version of the current commit ID.
      type: string
      sample: "9fceb02"
    commit_date:
      description:
        - Commit date of the current HEAD in the format YYYY-MM-DD HH:MM:SS.
      type: string
      sample: "2025-08-03 12:34:56"
failed:
  description:
    - Indicates if the module execution failed.
  returned: always
  type: bool
msg:
  description:
    - Error message in case of failure.
  returned: on failure
  type: string
"""

# ----------------------------------------------------------------------


class GitInfo(object):
    """ """

    module = None

    def __init__(self, module):
        """ """
        self.module = module

        self.work_dir = module.params.get("work_dir")

    def run(self):
        """ """
        if self.work_dir:
            os.chdir(self.work_dir)
        else:
            return dict(failed=True, msg=f"work_dir {self.work_dir} does not exist.")

        return self.git_info()

    def git_info(self):
        """ """
        git_version = None
        git_commit_short = None
        git_commit_date = None

        try:
            repo = git.Repo(search_parent_directories=True)
        except (git.InvalidGitRepositoryError, git.NoSuchPathError):
            return dict(failed=True, msg="Error: No valid Git repository was found.")

        except Exception as e:
            return dict(failed=True, msg=f"An unexpected error has occurred: {e}")

        try:
            if repo.head.is_detached:
                try:
                    git_latest_tag = repo.git.describe("--tags", "--exact-match")
                    # use the git tag as branch name
                    git_current_branch = git_latest_tag
                except git.GitCommandError:
                    # we have no git tag
                    git_latest_tag = None
                    git_current_branch = "detached"
            else:
                git_current_branch = repo.active_branch.name
                git_latest_tag = next(
                    (
                        tag.name
                        for tag in sorted(
                            repo.tags,
                            key=lambda t: t.commit.committed_datetime,
                            reverse=True,
                        )
                    ),
                    None,
                )

            git_commit_short = repo.git.rev_parse("--short", "HEAD")
            git_commit_date = repo.head.commit.committed_datetime
            git_commit_id = repo.commit(git_current_branch).hexsha
            git_commit_lastid = next(repo.iter_commits(all=True)).hexsha
            git_latest_tag = next(
                (
                    tag.name
                    for tag in sorted(
                        repo.tags,
                        key=lambda t: t.commit.committed_datetime,
                        reverse=True,
                    )
                ),
                None,
            )
        except (git.InvalidGitRepositoryError, git.NoSuchPathError):
            return dict(failed=True, msg="Error: No valid Git repository was found.")

        except Exception as e:
            return dict(failed=True, msg=f"An unexpected error has occurred: {e}")

        try:
            if git_current_branch in ["master", "main"]:
                git_version = git_latest_tag

            elif git_current_branch == "nightly":
                upstream_commit = repo.git.rev_parse("@{upstream}")
                git_version = repo.git.rev_parse("--short", upstream_commit)
            elif not git_current_branch:
                repo.git.describe("--tags", "--exact-match")
            else:
                git_version = repo.git.rev_parse("--short", "HEAD")

            # Does the branch have an upstream?
            # try:
            #     upstream_branch = repo.git.rev_parse("--abbrev-ref", "--symbolic-full-name", f"{git_current_branch}@{{upstream}}")
            #     git_commit_date = repo.git.log("-1", "--format=%ci", upstream_branch)
            # except git.GitCommandError:
            #     self.module.log(f"Warning: There is no upstream branch configured for '{git_current_branch}'.")
            #     pass
            # except Exception as e:
            #     self.module.log(f"An unexpected error has occurred: {e}")
            #     pass

            result = {
                "version": git_version,
                "branch": git_current_branch,
                "latest_tag": git_latest_tag,
                "commit_id": git_commit_id,
                "last_commit_id": git_commit_lastid,
                "commit_short_id": git_commit_short,
                "commit_date": git_commit_date.strftime("%Y-%m-%d %H:%M:%S"),
            }

            return dict(failed=False, git=result)

        except git.GitCommandError as e:
            return dict(failed=True, msg=f"An error has occurred when calling git: {e}")
        except Exception as e:
            return dict(failed=True, msg=f"An unexpected error has occurred: {e}")


def main():

    specs = dict(
        work_dir=dict(required=True, type="path"),
    )

    module = AnsibleModule(
        argument_spec=specs,
        supports_check_mode=True,
    )

    m = GitInfo(module)
    result = m.run()

    module.log(msg=f"= result: {result}")

    module.exit_json(**result)


# import module snippets
if __name__ == "__main__":
    main()
