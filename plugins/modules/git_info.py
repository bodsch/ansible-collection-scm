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

short_description: TBD
description:
    - TBD

options:
  verbose:
    description: TBD
    required: false
    type: str
"""

EXAMPLES = r"""
"""

RETURN = r"""
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

        return dict(
            failed=False,
            changed=False,
            git=self.git_info()
        )

    def git_info(self):
        """
        """
        git_version = None
        # git_commit = None
        git_commit_short = None
        git_commit_date = None

        try:
            repo = git.Repo(search_parent_directories=True)
        except (git.InvalidGitRepositoryError, git.NoSuchPathError):
            self.module.log("Error: No valid Git repository was found.")
            return None
        except Exception as e:
            self.module.log(f"An unexpected error has occurred: {e}")
            return None

        git_current_branch = repo.active_branch.name

        git_commit_short = repo.git.rev_parse("--short", "HEAD")
        git_commit_date = repo.head.commit.committed_datetime
        git_commit_id = repo.commit(git_current_branch).hexsha
        git_commit_lastid = next(repo.iter_commits(all=True)).hexsha
        git_latest_tag = next(
            (tag.name for tag in sorted(repo.tags, key=lambda t: t.commit.committed_datetime, reverse=True)), None
        )

        try:
            if git_current_branch == "master":
                git_version = git_latest_tag

            elif git_current_branch == "nightly":
                upstream_commit = repo.git.rev_parse("@{upstream}")
                git_version = repo.git.rev_parse("--short", upstream_commit)
            else:
                git_version = repo.git.rev_parse("--short", "HEAD")

            # Does the branch have an upstream?
            try:
                upstream_branch = repo.git.rev_parse("--abbrev-ref", "--symbolic-full-name", f"{git_current_branch}@{{upstream}}")
                git_commit_date = repo.git.log("-1", "--format=%ci", upstream_branch)
            except git.GitCommandError:
                self.module.log(f"Warning: There is no upstream branch configured for '{git_current_branch}'.")
                pass
            except Exception as e:
                self.module.log(f"An unexpected error has occurred: {e}")
                pass

            result = {
                "version": git_version,
                "branch": git_current_branch,
                "latest_tag": git_latest_tag,
                "commit_id": git_commit_id,
                "last_commit_id": git_commit_lastid,
                "commit_short_id": git_commit_short,
                "commit_date": git_commit_date.strftime("%Y-%m-%d %H:%M:%S"),
            }

        except git.GitCommandError as e:
            self.module.log(f"An error has occurred when calling git: {e}")
            return None
        except Exception as e:
            self.module.log(f"An unexpected error has occurred: {e}")
            return None

        return result


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
