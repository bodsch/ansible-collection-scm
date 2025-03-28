#!/usr/bin/python3
# -*- coding: utf-8 -*-

# (c) 2024-2025, Bodo Schulz <bodo@boone-schulz.de>
# Apache (see LICENSE or https://opensource.org/licenses/Apache-2.0)

from __future__ import absolute_import, division, print_function
import git
import os

from ansible.module_utils.basic import AnsibleModule

DOCUMENTATION = r"""
---
module: git_info
author: Bodo 'bodsch' Schulz <bodo@boone-schulz.de>
version_added: 1.3.0

short_description: Organise various information from a git repository.
description:
    - Organise various information from a git repository.

options:
  work_dir:
    description: Directory from which the git information is to be retrieved.
    required: true
    type: path
"""

EXAMPLES = r"""
- name: obtain git information from download path
  become: true
  bodsch.scm.git_info:
    work_dir: "{{ mailcow_tmp_directory }}"
  register: mailcow_repository_information

- name: obtain git information from install path
  become: true
  bodsch.scm.git_info:
    work_dir: "{{ mailcow_install_path }}/active"
  register: mailcow_installed_information
"""

RETURN = r"""

branch:
    description:
        - the branch name.
    type: string
commit_date:
    description:
        - The commit date in the respective branch.
    type: string
commit_id:
    description:
        - The full commit ID.
    type: string
commit_short_id:
    description:
        - The short version of the commit ID.
    type: string
last_commit_id:
    description:
        - The last commit ID in the repository.
    type: string
latest_tag:
    description:
        - The last git tag in the repository.
    type: string
version:
    description:
        - A version is defined here depending on the branch.
        - If it is a master / main branch, the last git tag is returned here.
        - Otherwise the short commit id is used.
    type: string
"""

# ----------------------------------------------------------------------


class GitInfo(object):
    """
    """
    module = None

    def __init__(self, module):
        """
        """
        self.module = module

        self.work_dir = module.params.get("work_dir")

    def run(self):
        """
        """
        if self.work_dir:
            os.chdir(self.work_dir)
        else:
            return dict(
                failed=True,
                msg=f"work_dir {self.work_dir} does not exist."
            )

        return self.git_info()

    def git_info(self):
        """
        """
        git_version = None
        git_commit_short = None
        git_commit_date = None

        try:
            repo = git.Repo(search_parent_directories=True)
        except (git.InvalidGitRepositoryError, git.NoSuchPathError):
            return dict(
                failed=True,
                msg="Error: No valid Git repository was found."
            )

        except Exception as e:
            return dict(
                failed=True,
                msg=f"An unexpected error has occurred: {e}"
            )

        try:
            if repo.head.is_detached:
                try:
                    git_latest_tag = repo.git.describe('--tags', '--exact-match')
                    # use the git tag as branch name
                    git_current_branch = git_latest_tag
                except git.GitCommandError:
                    # we have no git tag
                    git_latest_tag = None
                    git_current_branch = "detached"
            else:
                git_current_branch = repo.active_branch.name
                git_latest_tag = next(
                    (tag.name for tag in sorted(repo.tags, key=lambda t: t.commit.committed_datetime, reverse=True)), None
                )

            git_commit_short = repo.git.rev_parse("--short", "HEAD")
            git_commit_date = repo.head.commit.committed_datetime
            git_commit_id = repo.commit(git_current_branch).hexsha
            git_commit_lastid = next(repo.iter_commits(all=True)).hexsha
            git_latest_tag = next(
                (tag.name for tag in sorted(repo.tags, key=lambda t: t.commit.committed_datetime, reverse=True)), None
            )
        except (git.InvalidGitRepositoryError, git.NoSuchPathError):
            return dict(
                failed=True,
                msg="Error: No valid Git repository was found."
            )

        except Exception as e:
            return dict(
                failed=True,
                msg=f"An unexpected error has occurred: {e}"
            )

        try:
            if git_current_branch in ["master", "main"]:
                git_version = git_latest_tag

            elif git_current_branch == "nightly":
                upstream_commit = repo.git.rev_parse("@{upstream}")
                git_version = repo.git.rev_parse("--short", upstream_commit)
            elif not git_current_branch:
                repo.git.describe('--tags', '--exact-match')
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

            return dict(
                failed=False,
                git=result
            )

        except git.GitCommandError as e:
            return dict(
                failed=True,
                msg=f"An error has occurred when calling git: {e}"
            )
        except Exception as e:
            return dict(
                failed=True,
                msg=f"An unexpected error has occurred: {e}"
            )


def main():

    specs = dict(
        work_dir=dict(
            required=True,
            type='path'
        ),
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
if __name__ == '__main__':
    main()
