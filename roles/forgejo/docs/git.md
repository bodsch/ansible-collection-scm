## git
```yaml
forgejo_git:
  path: ""
  home_path: ""                                   # "%(app_data_path)s/home"
  disable_diff_highlight: ""                      # false
  max_git_diff_lines: ""                          # 1000
  max_git_diff_line_characters: ""                # 5000
  max_git_diff_files: ""                          # 100
  commits_range_size: ""                          # 50
  branches_range_size: ""                         # 20
  gc_args: ""
  enable_auto_git_wire_protocol: ""               # true
  pull_request_push_message: ""                   # true
  large_object_threshold: ""                      # 1048576
  disable_core_protect_ntfs: ""                   # false
  disable_partial_clone: ""                       # false
  # changes between 1.20 and 9.0
  grep: ""                                        # 2
  verbose_push: ""                                # true
  verbose_push_delay: ""                          # 5s
  # git operation timeout in seconds
  timeout:
    default: ""                                   # 360
    migrate: ""                                   # 600
    mirror: ""                                    # 300
    clone: ""                                     # 300
    pull: ""                                      # 300
    gc: ""                                        # 60
  # git reflog timeout in days
  reflog:
    enabled: ""                                   # true
    expiration: ""                                # 90
  config:
    diff.algorithm: histogram
    core.logAllRefUpdates: true
    gc.reflogExpire: 90
```
