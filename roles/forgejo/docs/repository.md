## repository
```yaml
forgejo_repository:
  root: ""
  script_type: bash
  detected_charsets_order: []                     # [UTF-8, UTF-16BE, UTF-16LE, UTF-32BE, UTF-32LE, ISO-8859, ...]
  ansi_charset: ""
  force_private: ""                               # false
  default_private: ""                             # last
  default_push_create_private: ""                 # true
  max_creation_limit: ""                          # -1
  mirror_queue_length: ""                         # 1000
  pull_request_queue_length: ""                   # 1000
  preferred_licenses: []                          # [Apache License 2.0, MIT License]
  disable_http_git: ""                            # false
  access_control_allow_origin: ""
  use_compat_ssh_uri: ""                          # false
  go_get_clone_url_protocol: ""                   # https
  default_close_issues_via_commits_in_any_branch: "" # false
  enable_push_create_user: ""                     # false
  enable_push_create_org: ""                      # false
  disabled_repo_units: []                         # allowed values: repo.issues, repo.ext_issues, repo.pulls, repo.wiki, repo.ext_wiki, repo.projects, repo.packages, repo.actions.
  default_repo_units: []                          # allowed values: repo.code, repo.releases, repo.issues, repo.pulls, repo.wiki, repo.projects, repo.packages, repo.actions.
  default_fork_repo_units: []                     # [repo.code, repo.pulls]
  prefix_archive_files: ""                        # true
  disable_migrations: ""                          # false
  disable_stars: ""                               # false
  disable_forks: ""                               # false
  default_branch: ""                              # main
  allow_adoption_of_unadopted_repositories: ""    # false
  allow_deletion_of_unadopted_repositories: ""    # false
  disable_download_source_archives: ""            # false
  allow_fork_without_maximum_limit: ""            # true
  editor:
    line_wrap_extensions: []                      # [.txt, .md, .markdown, .mdown, .mkd]
  local:
    local_copy_path: ""                           # tmp/local-repo
  upload:
    enabled: ""                                   # true
    temp_path: ""                                 # data/tmp/uploads
    allowed_types: []
    file_max_size: ""                             # 3
    max_files: ""                                 # 5
  pull_request:
    work_in_progress_prefixes: []                 # ["WIP:", "[WIP]"]
    close_keywords: []                            # [close, closes, closed, fix, fixes, fixed, resolve, resolves, resolved]
    reopen_keywords: []                           # [reopen, reopens, reopened]
    default_merge_style: ""                       # merge
    default_merge_message_commits_limit: ""       # 50
    default_merge_message_size: ""                # 5120
    default_merge_message_all_authors: ""         # false
    default_merge_message_max_approvers: ""       # 10
    default_merge_message_official_approvers_only: "" # true
    add_co_committer_trailers: ""                 # true
    test_conflicting_patches_with_git_apply: ""   # false
    populate_squash_comment_with_commit_messages: "" # true
    retarget_children_on_merge: ""                # true
  issue:
    lock_reasons: []                              # [Too heated, Off-topic, Resolved, Spam]
  release:
    allowed_types: []
    default_paging_num: ""                        # 10
  signing:
    signing_key: ""                               # default
    signing_name: ""
    signing_email: ""
    default_trust_model: ""                       # collaborator
    initial_commit: []                            # [always]
    crud_actions: []                              # [pubkey, twofa, parentsigned]
    wiki: []                                      # [never]
    merges: []                                    # [pubkey, twofa, basesigned, commitssigned]
  mimetype_mapping: {}
  #  .apk: application/vnd.android.package-archive
```
