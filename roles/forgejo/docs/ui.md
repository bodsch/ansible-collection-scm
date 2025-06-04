## ui
```yaml
forgejo_ui:
  explore_paging_num: ""                          # 20
  issue_paging_num: ""                            # 20
  feed_max_commit_num: ""                         # 5
  feed_paging_num: ""                             # 20
  sitemap_paging_num: ""                          # 20
  graph_max_commit_num: ""                        # 100
  code_comment_lines: ""                          # 4
  theme_color_meta_tag: ""                        # "#6cc644"
  max_display_file_size: ""                       # 8388608
  show_user_email: ""                             # true
  default_theme: ""                               # auto
  themes: []                                      # [auto, forgejo, arc-green]
  reactions: []                                   # ["+1", "-1", laugh, hooray, confused, heart, rocket, eyes]
  custom_emojis: []                               # [forgejo, codeberg, gitlab, git, github, gogs]
  default_show_full_name: ""                      # false
  search_repo_description: ""                     # true
  use_service_worker: ""                          # false
  only_show_relevant_repos: ""                    # false
  ambiguous_unicode_detection: ""                 # true
  reaction_max_user_num: ""                       # 10
  explore_paging_default_sort: ""                 # "recentupdate" or "alphabetically", "reverselastlogin", "newest", "oldest"
  preferred_timestamp_tense: ""                   # `absolute` time (i.e. 1970-01-01, 11:59) | `mixed` means most timestamps are rendered in relative time (i.e. 2 days ago)
  repo_search_paging_num: ""                      # 20
  members_paging_num: ""                          # 20
  packages_paging_num: ""                         # 20
  admin:
    user_paging_num: ""                           # 50
    repo_paging_num: ""                           # 50
    notice_paging_num: ""                         # 25
    org_paging_num: ""                            # 50
  user:
    repo_paging_num: ""                           # 15
  meta:
    author: ""                                    # forgejo - git with a cup of tea
    description: ""                               # forgejo (git with a cup of tea) is a painless self-hosted Git service written in Go
    keywords: []                                  # [go, git, self-hosted, forgejo]
  notification:
    min_timeout: ""                               # 10s
    max_timeout: ""                               # 60s
    timeout_step: ""                              # 10s
    event_source_update_time: ""                  # 10s
  svg:
    enable_render: ""                             # true
  csv:
    max_file_size: ""                             # 524288
    max_rows: ""                                  # 2500
```
