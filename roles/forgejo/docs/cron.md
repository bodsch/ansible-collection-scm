## cron
```yaml
forgejo_cron:
  enabled: true                                   # true
  run_at_start: true                              # true
  # Note: ``SCHEDULE`` accept formats
  #    - Full crontab specs, e.g. "* * * * * ?"
  #    - Descriptors, e.g. "@midnight", "@every 1h30m"
  archive_cleanup:
    comment: ""                                   #
    enabled: true
    run_at_start: true
    notice_on_success: false
    schedule: "@midnight"
    older_than: 24h
  update_mirrors:
    comment: ""
    enabled: true
    run_at_start: false
    notice_on_success: false
    schedule: "@every 10m"
    pull_limit: 50
    push_limit: 50
  repo_health_check:
    comment: ""
    enabled: true
    run_at_start: false
    notice_on_success: false
    schedule: "@midnight"
    timeout: 60s
    args: ""
    #  arguments for command 'git fsck', e.g. "--unreachable --tags"
    #  see more on http://git-scm.com/docs/git-fsck
  check_repo_stats:
    comment: "Check repository statistics"
    enabled: true
    run_at_start: true
    notice_on_success: false
    schedule: "@midnight"
  update_migration_poster_id:
    comment: ""
    enabled: true
    run_at_start: true
    notice_on_success: false
    schedule: "@midnight"
  sync_external_users:
    comment: Synchronize external user data (only LDAP user synchronization is supported)
    enabled: true
    run_at_start: false
    notice_on_success: false
    schedule: "@midnight"
    update_existing: true
  cleanup_actions:
    comment: Cleanup expired actions assets
    enabled: true
    run_at_start: false
    schedule: "@midnight"
  deleted_branches_cleanup:
    comment: clean-up deleted branches
    enabled: true
    run_at_start: true
    notice_on_success: false
    schedule: "@midnight"
    older_than: 24h
  cleanup_hook_task_table:
    comment: cleanup hook_task table
    enabled: true
    run_at_start: false
    schedule: "@midnight"
    cleanup_type: olderthan
    older_than: 168h
    number_to_keep: 10
  cleanup_packages:
    comment: cleanup expired packages
    enabled: true
    run_at_start: true
    notice_on_success: false
    schedule: "@midnight"
    older_than: 24h
  # Extended cron task - not enabled by default
  delete_inactive_accounts:
    comment: delete all unactivated accounts
    enabled: false
    run_at_start: false
    notice_on_success: false
    schedule: "@annually"
    older_than: 168h
  delete_repo_archives:
    comment: delete all repository archives
    enabled: false
    run_at_start: false
    notice_on_success: false
    schedule: "@annually"
  git_gc_repos:
    comment: garbage collect all repositories
    enabled: false
    run_at_start: false
    notice_on_success: false
    schedule: "@every 72h"
    timeout: 60s
    #  arguments for command 'git gc'
    #  the default value is same with [git] -> GC_ARGS
    args: ""
  resync_all_sshkeys:
    comment: update the '.ssh/authorized_keys' file with Gitea SSH keys
    enabled: false
    run_at_start: false
    notice_on_success: false
    schedule: "@every 72h"
  resync_all_hooks:
    comment: resynchronize pre-receive, update and post-receive hooks of all repositories.
    enabled: false
    run_at_start: false
    notice_on_success: false
    schedule: "@every 72h"
  reinit_missing_repos:
    comment: reinitialize all missing git repositories for which records exist
    enabled: false
    run_at_start: false
    notice_on_success: false
    schedule: "@every 72h"
  delete_missing_repos:
    comment: delete all repositories missing their Git files
    enabled: false
    run_at_start: false
    notice_on_success: false
    schedule: "@every 72h"
  delete_generated_repository_avatars:
    comment: delete generated repository avatars
    enabled: false
    run_at_start: false
    notice_on_success: false
    schedule: "@every 72h"
  delete_old_actions:
    comment: delete all old actions from database
    enabled: false
    run_at_start: false
    notice_on_success: false
    schedule: "@every 168h"
    older_than: 8760h
  update_checker:
    comment: check for new forgejo versions
    enabled: true
    run_at_start: false
    enable_success_notice: false
    schedule: "@every 168h"
    http_endpoint: https://dl.forgejo.io/forgejo/version.json
  delete_old_system_notices:
    comment: delete all old system notices from database
    enabled: false
    run_at_start: false
    no_success_notice: false
    schedule: "@every 168h"
    older_than: 8760h
  gc_lfs:
    comment: garbage collect lfs pointers in repositories
    enabled: false
    run_at_start: false
    schedule: "@every 24h"
    older_than: 168h
    last_updated_more_than_ago: 72h
    number_to_check_per_repo: 100
    proportion_to_check_per_repo: 0.6

```
