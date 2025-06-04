## actions
```yaml
forgejo_actions:
  enabled: true                                   #
  default_actions_url: ""                         #
  artifact_retention_days: 90                     # 90
  zombie_task_timeout: ""                         #
  endless_task_timeout: ""                        #
  abandoned_job_timeout: ""                       #
  skip_workflow_strings:                          #
    - "[skip ci]"
    - "[ci skip]"
    - "[no ci]"
    - "[skip actions]"
    - "[actions skip]"
  # changes between 1.20 and 9.0
  log_compression: zstd                           #
  log_retention_days: 365                         #
  limit_dispatch_inputs: 10                       #
```
