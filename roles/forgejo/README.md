
# Ansible Role:  `bodsch.scm.forgejo`

Ansible role to install and configure [forgejo](https://forgejo.org/) on various linux systems.

Forgejo is a self-hosted lightweight software forge.
Easy to install and low maintenance, it just does the job.


[![GitHub Workflow Status](https://img.shields.io/github/actions/workflow/status/bodsch/ansible-forgejo/main.yml?branch=main)][ci]
[![GitHub issues](https://img.shields.io/github/issues/bodsch/ansible-forgejo)][issues]
[![GitHub release (latest by date)](https://img.shields.io/github/v/release/bodsch/ansible-forgejo)][releases]
[![Ansible Quality Score](https://img.shields.io/ansible/quality/50067?label=role%20quality)][quality]

[ci]: https://github.com/bodsch/ansible-forgejo/actions
[issues]: https://github.com/bodsch/ansible-forgejo/issues?q=is%3Aopen+is%3Aissue
[releases]: https://github.com/bodsch/ansible-forgejo/releases
[quality]: https://galaxy.ansible.com/bodsch/forgejo


## Requirements & Dependencies


### Operating systems

Tested on

* Arch Linux
* Debian based
    - Debian 10 / 11 / 12
    - Ubuntu 20.04 / 22.04

## usage

[config cheat-sheet](https://forgejo.org/docs/latest/admin/config-cheat-sheet)

- [actions](docs/actions.md)
- [admin](docs/admin.md)
- [api](docs/api.md)
- [attachment](docs/attachment.md)
- [badges](docs/badges.md)
- [cache](docs/cache.md)
- [camo](docs/camo.md)
- [cors](docs/cors.md)
- [cron](docs/cron.md)
- [database](docs/database.md)
- [email](docs/email.md)
- [f3](docs/f3.md)
- [federation](docs/federation.md)
- [git](docs/git.md)
- [highlight](docs/highlight.md)
- [i18n](docs/i18n.md)
- [indexer](docs/indexer.md)
- [lfs](docs/lfs.md)
- [log](docs/log.md)
- [mailer](docs/mailer.md)
- [markdown](docs/markdown.md)
- [markup](docs/markup.md)
- [metrics](docs/metrics.md)
- [migrations](docs/migrations.md)
- [mirror](docs/mirror.md)
- [oauth2_client](docs/oauth2_client.md)
- [oauth2](docs/oauth2.md)
- [openid](docs/openid.md)
- [other](docs/other.md)
- [packages](docs/packages.md)
- [picture](docs/picture.md)
- [project](docs/project.md)
- [proxy](docs/proxy.md)
- [queue](docs/queue.md)
- [repo_archive](docs/repo_archive.md)
- [repository](docs/repository.md)
- [security](docs/security.md)
- [server](docs/server.md)
- [service](docs/service.md)
- [session](docs/session.md)
- [ssh](docs/ssh.md)
- [storage](docs/storage.md)
- [task](docs/task.md)
- [time](docs/time.md)
- [ui](docs/ui.md)
- [webhook](docs/webhook.md)

### Examples

- [configured](molecule/configured/group_vars/all/vars.yml)
- [configured with ldap](molecule/configured-with-ldap/group_vars/all/vars.yml)
- [configured with mariadb](molecule/configured-with-mariadb/group_vars/all/vars.yml)
- [custom config directory](molecule/custom-config-directory/group_vars/all/vars.yml)
- [update](molecule/update/group_vars/all/vars.yml)


### Full example

```yaml
forgejo_version: 1.20.5-0

forgejo_system_user: forgejo
forgejo_system_group: forgejo
forgejo_config_dir: /etc/forgejo
forgejo_working_dir: /var/lib/forgejo
forgejo_data_dir: /home/{{ forgejo_system_user }}

forgejo_systemd:
  unit:
    after:
      - syslog.target
      - network.target
    wants: []
    requires: []

forgejo_release: {}

forgejo_direct_download: false

forgejo_name: "Forgejo – Beyond coding. We forge."
# Either "dev", "prod" or "test", default is "prod"
forgejo_run_mode: "prod"

forgejo_admin_user:
  username: "root"
  password: "change-it-ASAP!"
  email: "root@example.com"

forgejo_actions:
  enabled: false
  default_actions_url: ""

forgejo_admin:
  # Disallow regular (non-admin) users from creating organizations.
  disable_regular_org_creation: ""                # false
  # Default configuration for email notifications for users (user configurable).
  # Options: enabled, onmention, disabled
  default_email_notifications: ""                 # enabled

forgejo_api:
  enable_swagger: ""                              # true
  max_response_items: ""                          # 50
  default_paging_num: ""                          # 30
  default_git_trees_per_page: ""                  # 1000
  default_max_blob_size: ""                       # 10485760

forgejo_attachment:
  enabled: true
  # list of allowed file extensions (`.zip`),
  # mime types (`text/plain`) or
  # wildcard type (`image/*`, `audio/*`, `video/*`).
  # Empty value or `*/*` allows all types.
  allowed_types:
    - "image/*"
    # - ".csv"
    # - ".docx"
    # - ".fodg"
    # - ".fodp"
    # - ".fods"
    # - ".fodt"
    # - ".gif"
    # - ".gz"
    # - ".jpeg"
    # - ".jpg"
    # - ".log"
    # - ".md"
    # - ".mov"
    # - ".mp4"
    # - ".odf"
    # - ".odg"
    # - ".odp"
    # - ".ods"
    # - ".odt"
    # - ".patch"
    # - ".pdf"
    # - ".png"
    # - ".pptx"
    # - ".svg"
    # - ".tgz"
    # - ".txt"
    # - ".webm"
    # - ".xls"
    # - ".xlsx"
    # - ".zip"
  max_size: 4
  max_files: 5
  storage_type: local
  serve_direct: false
  path: data/attachments
  minio:
    endpoint: localhost:9000
    access_key_id: ""
    secret_access_key: ""
    bucket: forgejo
    location: us-east-1
    base_path: attachments/
    use_ssl: false
    insecure_skip_verify: false
    checksum_algorithm: default

forgejo_cache:
  enabled: true
  # either "memory", "redis", "memcache", or "twoqueue". default is "memory"
  adapter: memory
  interval: 60
  # ;; for "redis" and "memcache", connection host address
  # ;; redis: `redis://127.0.0.1:6379/0?pool_size=100&idle_timeout=180s`
  # ;; memcache: `127.0.0.1:11211`
  # ;; twoqueue: `{"size":50000,"recent_ratio":0.25,"ghost_ratio":0.5}` or `50000`
  host: ""
  item_ttl: 16h
  last_commit:
    enabled: true
    item_ttl: 8760h
    commits_count: 1000

forgejo_camo:
  enabled: false
  # ; url to a camo image proxy, it **is required** if camo is enabled.
  server_url: ""
  # ; hmac to encode urls with, it **is required** if camo is enabled.
  hmac_key: ""
  # ; set to true to use camo for https too lese only non https urls are proxyed
  allways: false

forgejo_cors:
  enabled: false
  scheme: http
  allow_domain:
    - "*"
  allow_subdomain: false
  methods:
    - get
    - head
    - POST
    - PUT
    - PATCH
    - DELETE
    - OPTIONS
  max_age: 10m
  allow_credentials: false
  headers:
    - Content-Type
    - User-Agent
  x_frame_options:
    - SAMEORIGIN

forgejo_cron:
  enabled: true
  run_at_start: false
  # Note: ``SCHEDULE`` accept formats
  #    - Full crontab specs, e.g. "* * * * * ?"
  #    - Descriptors, e.g. "@midnight", "@every 1h30m"
  archive_cleanup:
    comment: ""
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

forgejo_database:
  db_type: sqlite3
  # mariadb configuration
  host: ""                        # 127.0.0.1:3306 ; can use socket e.g. /var/run/mysqld/mysqld.sock
  name: ""                        # forgejo
  user: ""                        # root
  passwd: ""                      # ;use passwd: `your password` for quoting if you use special characters in the password.
  ssl_mode: ""                    # false ; either "false" (default), "true", or "skip-verify"
  charset: ""                     # utf8mb4 ;either "utf8" or "utf8mb4", default is "utf8mb4".
  # ; postgres configuration
  # db_type: postgres
  # host: 127.0.0.1:5432 ; can use socket e.g. /var/run/postgresql/
  # name: forgejo
  # user: root
  # passwd =
  # schema =
  # ssl_mode=disable ;either "disable" (default), "require", or "verify-full"
  # sqlite configuration
  path: data/forgejo.db             #
  sqlite_timeout: ""              # query timeout defaults to: 500
  sqlite_journal_mode: ""         # defaults to sqlite database default (often delete), can be used to enable wal mode. https://www.sqlite.org/pragma.html#pragma_journal_mode
  # mssql configuration
  # db_type: mssql
  # host: 172.17.0.2:1433
  # name: forgejo
  # user: sa
  # passwd: mwantsasecurepassword1
  iterate_buffer_size: 50
  log_sql: false
  # ;
  # ; maximum number of db connect retries
  db_retries: 10
  # ;
  # ; backoff time per db retry (time.duration)
  db_retry_backoff: 3s
  # ;
  # ; max idle database connections on connection pool, default is 2
  max_idle_conns: 2
  # ;
  # ; database connection max life time, default is 0 or 3s mysql (see #6804 & #7071 for reasoning)
  conn_max_lifetime: 3s
  # ;
  # ; database maximum number of open connections, default is 0 meaning no maximum
  max_open_conns: 0
  # ;
  # ; whether execute database models migrations automatically
  auto_migration: true

forgejo_email:
  incoming:
    enabled: false
    #
    # the email address including the %{token} placeholder that will be replaced per user/action.
    # example: incoming+%{token}@example.com
    # the placeholder must appear in the user part of the address (before the @).
    reply_to_address: ""
    #
    # imap server host
    host: ""
    #
    # imap server port
    port: ""
    #
    # username of the receiving account
    username: ""
    #
    # password of the receiving account
    password: ""
    #
    # whether the imap server uses tls.
    use_tls: false
    #
    # if set to true, completely ignores server certificate validation errors. This option is unsafe.
    skip_tls_verify: true
    #
    # the mailbox name where incoming mail will end up.
    mailbox: inbox
    #
    # whether handled messages should be deleted from the mailbox.
    delete_handled_message: true
    #
    # maximum size of a message to handle. Bigger messages are ignored. Set to 0 to allow every size.
    maximum_message_size: 10485760

forgejo_federation:
  enabled: false
  share_user_statistics: true
  max_size: 4
  algorithms:
    - rsa-sha256
    - rsa-sha512
    - ed25519
  digest_algorithm: SHA-256
  get_headers:
    - "(request-target)"
    - Date
  post_headers:
    - "(request-target)"
    - Date
    - Digest

forgejo_git:
  path: ""
  home_path: "%(app_data_path)s/home"
  disable_diff_highlight: false
  max_git_diff_lines: 1000
  max_git_diff_line_characters: 5000
  max_git_diff_files: 100
  commits_range_size: 50
  branches_range_size: 20
  gc_args: ""
  enable_auto_git_wire_protocol: true
  pull_request_push_message: true
  large_object_threshold: 1048576
  disable_core_protect_ntfs: false
  disable_partial_clone: false
  # git operation timeout in seconds
  timeout:
    default: 360
    migrate: 600
    mirror: 300
    clone: 300
    pull: 300
    gc: 60
  # git reflog timeout in days
  reflog:
    enabled: true
    expiration: 90

forgejo_highlight:
  mapping:
    .toml: ini

forgejo_i18n:
  # The first locale will be used as the default if user browser's language doesn't match any locale in the list.
  langs:
    - en-US
    - de-DE
    - fr-FR
  names:
    - English,
    - Deutsch,
    - Français

forgejo_indexer:
  # issue indexer type, currently support: bleve, db, elasticsearch or meilisearch default is bleve
  issue_indexer_type: bleve
  # issue indexer storage path, available when ISSUE_INDEXER_TYPE is bleve
  issue_indexer_path: indexers/issues.bleve
  # issue indexer connection string, available when ISSUE_INDEXER_TYPE is elasticsearch or meilisearch
  issue_indexer_conn_str: http://elastic:changeme@localhost:9200
  # issue indexer name, available when ISSUE_INDEXER_TYPE is elasticsearch
  issue_indexer_name: forgejo_issues
  # timeout the indexer if it takes longer than this to start.
  # set to -1 to disable timeout.
  startup_timeout: 30s
  # issue indexer queue, currently support: channel, levelqueue or redis, default is levelqueue (deprecated - use [queue.issue_indexer])
  issue_indexer_queue_type: levelqueue                      # ; **DEPRECATED** use settings in `[queue.issue_indexer]`.
  # when issue_indexer_queue_type is levelqueue, this will be the path where the queue will be saved.
  # this can be overridden by `issue_iNDEXER_QUEUE_CONN_STR`.
  # default is queues/common
  issue_indexer_queue_dir: queues/common                    # ; **DEPRECATED** use settings in `[queue.issue_indexer]`. Relative paths will be made absolute against `%(APP_DATA_PATH)s`.
  # when `issue_indexer_queue_type` is `redis`, this will store the redis connection string.
  # when `issue_indexer_queue_type` is `levelqueue`, this is a directory or additional options of
  # the form `leveldb://path/to/db?option=value&....`, and overrides `ISSUE_INDEXER_QUEUE_DIR`.
  issue_indexer_queue_conn_str: "addrs=127.0.0.1:6379 db=0" # ; **DEPRECATED** use settings in `[queue.issue_indexer]`.
  # batch queue number, default is 20
  issue_indexer_queue_batch_number: 20                      # ; **DEPRECATED** use settings in `[queue.issue_indexer]`.
  # repo indexer by default disabled, since it uses a lot of disk space
  repo_indexer_enabled: false
  # code search engine type, could be `bleve` or `elasticsearch`.
  repo_indexer_type: bleve
  # index file used for code search. available when `REPO_INDEXER_TYPE` is bleve
  repo_indexer_path: indexers/repos.bleve
  # code indexer connection string, available when `REPO_INDEXER_TYPE` is elasticsearch. i.e. http://elastic:changeme@localhost:9200
  repo_indexer_conn_str: ""
  # code indexer name, available when `REPO_INDEXER_TYPE` is elasticsearch
  repo_indexer_name: forgejo_codes
  # a comma separated list of glob patterns (see https://github.com/gobwas/glob) to include
  # in the index; default is empty
  repo_indexer_include: []
  # a comma separated list of glob patterns to exclude from the index; ; default is empty
  repo_indexer_exclude: []
  update_buffer_len: 20;                                    # **deprecated** use settings in `[queue.issue_indexer]`.
  max_file_size: 1048576

forgejo_lfs:
  # storage type, currently supported: local, minio
  storage_type: local
  path: data/lfs

  minio_base_path: ""
  minio_endpoint: ""
  minio_access_key_id: ""
  minio_secret_access_key: ""
  minio_bucket: ""
  minio_location: ""

forgejo_log:
  root_path: ""
  mode:
    - console
    - file
  level: info
  disable_router_log: false
  router: console
  enable_access_log: false
  access: file
  # TODO
  access_log_template: ""
    # {{.Ctx.RemoteAddr}} - {{.Identity}}
    # {{.Start.Format "[02/Jan/2006:15:04:05 -0700]" }}
    # {{.Ctx.Req.Method}}
    # {{.Ctx.Req.URL.RequestURI}}
    # {{.Ctx.Req.Proto}}"
    # {{.ResponseWriter.Status}}
    # {{.ResponseWriter.Size}}
    # \"{{.Ctx.Req.Referer}}\" \"{{.Ctx.Req.UserAgent}}\"
  enable_ssh_log: false
  stacktrace_level: none
  buffer_len: 10000
  # # ;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;
  # #  creating specific log configuration
  # #
  # #  you can set specific configuration for individual modes and subloggers
  # #
  # #  configuration available to all log modes/subloggers
  # level: ""
  # flags: stdflags
  # expression: ""
  # prefix: ""
  # colorize: false
  console:
    #  for "console" mode only
    stderr: false
  file:
    #  for "file" mode only
    level: ""
    #  set the file_name for the logger. if this is a relative path this
    #  will be relative to root_path
    file_name: ""
    #  this enables automated log rotate(switch of following options), default is true
    log_rotate: true
    #  max size shift of a single file, default is 28 means 1 << 28, 256MB
    max_size_shift: 28
    #  segment log daily, default is true
    daily_rotate: true
    #  delete the log file after n days, default is 7
    max_days: 7
    #  compress logs with gzip
    compress: true
    #  compression level see godoc for compress/gzip
    compression_level: -1
  conn:
    #  for "conn" mode only
    level: ""
    #  reconnect host for every single message, default is false
    reconnect_on_msg: false
    #  try to reconnect when connection is lost, default is false
    reconnect: false
    #  either "tcp", "unix" or "udp", default is "tcp"
    protocol: tcp
    #  host address
    addr: ""
  smtp:
    #  for "smtp" mode only
    level: ""
    #  name displayed in mail title, default is "diagnostic message from server"
    subject: diagnostic message from server
    #  mail server
    host: ""
    #  mailer user name and password
    user: ""
    #  use passwd: `your password` for quoting if you use special characters in the password.
    passwd: ""
    #  receivers, can be one or more, e.g. 1@example.com,2@example.com
    receivers: ""

forgejo_mailer:
  enabled: false
  #
  # buffer length of channel, keep it as it is if you don't know what it is.
  send_buffer_len: 100
  #
  # prefix displayed before subject in mail
  subject_prefix: ""
  #
  # mail server protocol. one of "smtp", "smtps", "smtp+starttls", "smtp+unix", "sendmail", "dummy".
  # - sendmail: use the operating system's `sendmail` command instead of SMTP. This is common on Linux systems.
  # - dummy: send email messages to the log as a testing phase.
  # if your provider does not explicitly say which protocol it uses but does provide a port,
  # you can set smtp_port instead and this will be inferred.
  # (before 1.18, see the notice, this was controlled via MAILER_TYPE and IS_TLS_ENABLED.)
  protocol: ""
  #
  # mail server address, e.g. smtp.gmail.com.
  # for smtp+unix, this should be a path to a unix socket instead.
  # (before 1.18, see the notice, this was combined with SMTP_PORT as HOST.)
  smtp_addr: ""
  #
  # mail server port. common ports are:
  #   25:  insecure smtp
  #   465: smtp secure
  #   587: starttls
  # if no protocol is specified, it will be inferred by this setting.
  # (before 1.18, this was combined with SMTP_ADDR as HOST.)
  smtp_port: ""
  #
  # enable helo operation. defaults to true.
  enable_helo: true
  #
  # custom hostname for helo operation.
  # if no value is provided, one is retrieved from system.
  helo_hostname: ""
  #
  # if set to `true`, completely ignores server certificate validation errors.
  # this option is unsafe. consider adding the certificate to the system trust store instead.
  force_trust_server_cert: false
  #
  # use client certificate in connection.
  use_client_cert: false
  client_cert_file: custom/mailer/cert.pem
  client_key_file: custom/mailer/key.pem
  #
  # mail from address, rfc 5322. This can be just an email address, or the `"Name" <email@example.com>` format
  from: ""
  #
  # sometimes it is helpful to use a different address on the envelope. Set this to use ENVELOPE_FROM as the from on the envelope. Set to `<>` to send an empty address.
  envelope_from: ""
  #
  # mailer user name and password, if required by provider.
  user: ""
  #
  # use passwd: `your password` for quoting if you use special characters in the password.
  passwd: ""
  #
  # send mails only in plain text, without HTML alternative
  send_as_plain_text: false
  #
  # specify an alternative sendmail binary
  sendmail_path: sendmail
  #
  # specify any extra sendmail arguments
  # warning: if your sendmail program interprets options you should set this to "--" or terminate these args with "--"
  sendmail_args: ""
  #
  # timeout for sendmail
  sendmail_timeout: 5m
  #
  # convert \r\n to \n for sendmail
  sendmail_convert_crlf: true

forgejo_markdown:
  enable_hard_line_break_in_comments: true
  enable_hard_line_break_in_documents: false
  custom_url_schemes: []
  file_extensions:
    - ".md"
    - ".markdown"
    - ".mdown"
    - ".mkd"
  enable_math: true

forgejo_markup:
  mermaid_max_source_characters: 5000
  # the following keys can appear once to define a sanitation policy rule.
  # this section can appear multiple times by adding a unique alphanumeric suffix to define multiple rules.
  # e.g., [markup.sanitizer.1] -> [markup.sanitizer.2] -> [markup.sanitizer.TeX]
  sanitizer: []
  #  - id: 1
  #    element: span
  #    allow_attr: class
  #    regexp: ^(info|warning|error)$
  #  - id: 2
  #    element: div
  #    allow_attr: class
  #    regexp: ^(info|warning|error)$
  asciidoc:
    enabled: false
    file_extensions:
      - .adoc
      - .asciidoc
    render_command: "asciidoc --out-file=- -"
    is_input_file: false
    render_content_mode: sanitized

forgejo_metrics:
  enabled: false
  # if you want to add authorization, specify a token here
  token: ""
  # enable issue by label metrics; default is false
  enabled_issue_by_label: false
  # enable issue by repository metrics; default is false
  enabled_issue_by_repository: false

forgejo_migrations:
  max_attempts: 3
  retry_backoff: 3
  allowed_domains: []
  blocked_domains: []
  allow_localnetworks: false

forgejo_mirror:
  enabled: true
  disable_new_pull: false
  disable_new_push: false
  default_interval: 8h
  min_interval: 10m

forgejo_oauth2:
  enabled: true
  #
  # algorithm used to sign oauth2 tokens. Valid values: HS256, HS384, HS512, RS256, RS384, RS512, ES256, ES384, ES512, EdDSA
  jwt_signing_algorithm: RS256
  #
  # private key file path used to sign OAuth2 tokens. The path is relative to APP_DATA_PATH.
  # this setting is only needed if JWT_SIGNING_ALGORITHM is set to RS256, RS384, RS512, ES256, ES384 or ES512.
  # the file must contain a rsa or ECDSA private key in the PKCS8 format. If no key exists a 4096 bit key will be created for you.
  jwt_signing_private_key_file: jwt/private.pem
  #
  # oauth2 authentication secret for access and refresh tokens, change this yourself to a unique string. CLI generate option is helpful in this case. https://docs.forgejo.io/en-us/command-line/#generate
  # this setting is only needed if JWT_SIGNING_ALGORITHM is set to HS256, HS384 or HS512.
  jwt_secret: ""
  #
  # lifetime of an oauth2 access token in seconds
  access_token_expiration_time: 3600
  #
  # lifetime of an oauth2 refresh token in hours
  refresh_token_expiration_time: 730
  #
  # check if refresh token got already used
  invalidate_refresh_tokens: false
  #
  # maximum length of oauth2 token/cookie stored on server
  max_token_length: 32767

forgejo_oauth2_client:
  register_email_confirm: ""
  openid_connect_scopes: ""
  enable_auto_registration: false
  username: nickname
  update_avatar: false
  account_linking: login

forgejo_openid:
  # whether to allow signin in via OpenID
  enable_openid_signin: true
  #
  # whether to allow registering via OpenID
  # do not include to rely on rhw DISABLE_REGISTRATION setting
  enable_openid_signup: true
  #
  # allowed uri patterns (pOSIX regexp).
  # space separated.
  # only these would be allowed if non-blank.
  # example value: trusted.domain.org trusted.domain.net
  whitelisted_uris: []
  #
  # forbidden uri patterns (POSIX regexp).
  # space separated.
  # only used if whitelisteD_URIS is blank.
  # example value: loadaverage.org/badguy stackexchange.com/.*spammer
  blacklisted_uris: []

forgejo_other:
  show_footer_branding: false
  # show version information about Gitea and Go in the footer
  show_footer_version: true
  # show template execution time in the footer
  show_footer_template_load_time: true
  # generate sitemap. defaults to `true`.
  enable_sitemap: true
  # enable/disable rss/atom feed
  enable_feed: true

forgejo_packages:
  enabled: true
  #
  # path for chunked uploads. Defaults to APP_DATA_PATH + `tmp/package-upload`
  chunked_upload_path: tmp/package-upload
  #
  # maximum count of package versions a single owner can have (`-1` means no limits)
  limit_total_owner_count: -1
  # maximum size of packages a single owner can use (`-1` means no limits, format `1000`, `1 MB`, `1 GiB`)
  limit_total_owner_size: -1
  # maximum size of a cargo upload (`-1` means no limits, format `1000`, `1 MB`, `1 GiB`)
  limit_size_cargo: -1
  # maximum size of a chef upload (`-1` means no limits, format `1000`, `1 MB`, `1 GiB`)
  limit_size_chef: -1
  # maximum size of a composer upload (`-1` means no limits, format `1000`, `1 MB`, `1 GiB`)
  limit_size_composer: -1
  # maximum size of a conan upload (`-1` means no limits, format `1000`, `1 MB`, `1 GiB`)
  limit_size_conan: -1
  # maximum size of a conda upload (`-1` means no limits, format `1000`, `1 MB`, `1 GiB`)
  limit_size_conda: -1
  # maximum size of a container upload (`-1` means no limits, format `1000`, `1 MB`, `1 GiB`)
  limit_size_container: -1
  # maximum size of a generic upload (`-1` means no limits, format `1000`, `1 MB`, `1 GiB`)
  limit_size_generic: -1
  # maximum size of a helm upload (`-1` means no limits, format `1000`, `1 MB`, `1 GiB`)
  limit_size_helm: -1
  # maximum size of a maven upload (`-1` means no limits, format `1000`, `1 MB`, `1 GiB`)
  limit_size_maven: -1
  # maximum size of a npm upload (`-1` means no limits, format `1000`, `1 MB`, `1 GiB`)
  limit_size_npm: -1
  # maximum size of a nuget upload (`-1` means no limits, format `1000`, `1 MB`, `1 GiB`)
  limit_size_nuget: -1
  # maximum size of a pub upload (`-1` means no limits, format `1000`, `1 MB`, `1 GiB`)
  limit_size_pub: -1
  # maximum size of a pypI upload (`-1` means no limits, format `1000`, `1 MB`, `1 GiB`)
  limit_size_pypi: -1
  # maximum size of a rubyGems upload (`-1` means no limits, format `1000`, `1 MB`, `1 GiB`)
  limit_size_rubygems: -1
  # maximum size of a swift upload (`-1` means no limits, format `1000`, `1 MB`, `1 GiB`)
  limit_size_swift: -1
  # maximum size of a vagrant upload (`-1` means no limits, format `1000`, `1 MB`, `1 GiB`)
  limit_size_vagrant: -1

forgejo_picture:
  avatar_upload_path: data/avatars
  repository_avatar_upload_path: data/repo-avatars
  #
  # how forgejo deals with missing repository avatars
  # none: no avatar will be displayed; random = random avatar will be displayed; image = default image will be used
  repository_avatar_fallback: none
  repository_avatar_fallback_image: /img/repo_default.png
  #
  # max width and height of uploaded avatars.
  # this is to limit the amount of RAM used when resizing the image.
  avatar_max_width: 4096
  avatar_max_height: 3072
  #
  # the multiplication factor for rendered avatar images.
  # larger values result in finer rendering on HiDPI devices.
  avatar_rendered_size_factor: 3
  #
  # maximum allowed file size for uploaded avatars.
  # this is to limit the amount of RAM used when resizing the image.
  avatar_max_file_size: 1048576
  #
  # chinese users can choose "duoshuo"
  # or a custom avatar source, like: http://cn.gravatar.com/avatar/
  gravatar_source: gravatar
  #
  # this value will always be true in offline mode.
  disable_gravatar: true
  #
  # federated avatar lookup uses dNS to discover avatar associated
  # with emails, see https://www.libravatar.org
  # this value will always be false in offline mode or when Gravatar is disabled.
  enable_federated_avatar: false

forgejo_project:
  project_board_basic_kanban_type:
    - To Do
    - In Progress
    - Done
  project_board_bug_triage_type:
    - Needs Triage
    - High Priority
    - Low Priority
    - Closed

forgejo_proxy:
  # enable the proxy, all requests to external via HTTP will be affected
  proxy_enabled: false
  # proxy server uRL, support http://, https//, socks://, blank will follow environment http_proxy/https_proxy/no_proxy
  proxy_url: ""
  # comma separated list of host names requiring proxy. Glob patterns (*) are accepted; use ** to match all hosts.
  proxy_hosts: []

forgejo_queue:
  default:
    type: persistable-channel
    #
    # data-dir for storing persistable queues and level queues, individual queues will default to `queues/common` meaning the queue is shared.
    datadir: queues/ # Relative paths will be made absolute against `%(APP_DATA_PATH)s`.
    #
    # default queue length before a channel queue will block
    length: 20
    #
    # batch size to send for batched queues
    batch_length: 20
    #
    # connection string for redis queues this will store the redis connection string.
    # when `type` is `persistable-channel`, this provides a directory for the underlying leveldb
    # or additional options of the form `leveldb://path/to/db?option=value&....`, and will override `DATADIR`.
    conn_str: "addrs=127.0.0.1:6379 db=0"
    #
    # provides the suffix of the default redis/disk queue name - specific queues can be overridden within in their [queue.name] sections.
    queue_name: "_queue"
    #
    # provides the suffix of the default redis/disk unique queue set name - specific queues can be overridden within in their [queue.name] sections.
    set_name: "_unique"
    #
    # if the queue cannot be created at startup - level queues may need a timeout at startup - wrap the queue:
    wrap_if_necessary: true
    #
    # attempt to create the wrapped queue at max
    max_attempts: 10
    #
    # timeout queue creation
    timeout: 15m30s
    #
    # create a pool with this many workers
    workers: 0
    #
    # dynamically scale the worker pool to at this many workers
    max_workers: 10
    #
    # add boost workers when the queue blocks for BLOCK_TIMEOUT
    block_timeout: 1s
    #
    # remove the boost workers after BOOST_TIMEOUT
    boost_timeout: 5m
    #
    # during a boost add BOOST_WORKERS
    boost_workers: 1
  foo:
    type: persistable-channel

forgejo_repository:
  root: ""
  script_type: bash
  detected_charsets_order:
    - UTF-8
    - UTF-16BE
    - UTF-16LE
    - UTF-32BE
    - UTF-32LE
    - ISO-8859
    - windows-1252
    - windows-1250
    - windows-1253
    - windows-1255
    - windows-1251
    - windows-1256
    - KOI8-R
    - ISO-8859
    - windows-1254
    - Shift_JIS
    - GB18030
    - EUC-JP
    - EUC-KR
    - Big5
    - ISO-2022
    - IBM424_rtl
    - IBM424_ltr
    - IBM420_rtl
    - IBM420_ltr
  ansi_charset: ""
  force_private: false
  default_private: last
  default_push_create_private: true
  max_creation_limit: -1
  mirror_queue_length: 1000
  pull_request_queue_length: 1000
  preferred_licenses:
    - Apache License 2.0
    - MIT License
  disable_http_git: false
  access_control_allow_origin: ""
  use_compat_ssh_uri: false
  # comma separated list of globally disabled repo units.
  # allowed values: repo.issues, repo.ext_issues, repo.pulls, repo.wiki, repo.ext_wiki, repo.projects, repo.packages, repo.actions.
  disabled_repo_units: []
  #
  # comma separated list of default new repo units.
  # allowed values: repo.code, repo.releases, repo.issues, repo.pulls, repo.wiki, repo.projects, repo.packages, repo.actions.
  # note: code and releases can currently not be deactivated. if you specify default repo units you should still list them for future compatibility.
  # external wiki and issue tracker can't be enabled by default as it requires additional settings.
  # disabled repo units will not be added to new repositories regardless if it is in the default list.
  default_repo_units:
    - repo.code
    - repo.releases
    - repo.issues
    - repo.pulls
    - repo.wiki
    - repo.projects
    - repo.packages
  #
  # comma separated list of default forked repo units.
  # the set of allowed values and rules are the same as default_REPO_UNITS.
  default_fork_repo_units:
    - repo.code
    - repo.pulls
  prefix_archive_files: true
  disable_migrations: false
  disable_stars: false
  default_branch: main
  allow_adoption_of_unadopted_repositories: false
  allow_deletion_of_unadopted_repositories: false
  disable_download_source_archives: false
  allow_fork_without_maximum_limit: true

  editor:
    line_wrap_extensions:
      - .txt
      - .md
      - .markdown
      - .mdown
      - .mkd

  local:
    local_copy_path: tmp/local-repo

  upload:
    enabled: true
    temp_path: data/tmp/uploads
    allowed_types: []
    file_max_size: 3
    max_files: 5

  pull_request:
    work_in_progress_prefixes:
      - "WIP:"
      - "[WIP]"
    close_keywords:
      - close
      - closes
      - closed
      - fix
      - fixes
      - fixed
      - resolve
      - resolves
      - resolved
    reopen_keywords:
      - reopen
      - reopens
      - reopened
    default_merge_style: merge
    default_merge_message_commits_limit: 50
    default_merge_message_size: 5120
    default_merge_message_all_authors: false
    default_merge_message_max_approvers: 10
    default_merge_message_official_approvers_only: true
    add_co_committer_trailers: true
    test_conflicting_patches_with_git_apply: false

  issue:
    lock_reasons:
      - Too heated
      - Off-topic
      - Resolved
      - Spam

  release:
    allowed_types: []
    default_paging_num: 10

  signing:
    signing_key: default
    signing_name: ""
    signing_email: ""
    default_trust_model: collaborator
    initial_commit:
      - always
    crud_actions:
      - pubkey
      - twofa
      - parentsigned
    wiki:
      - never
    merges:
      - pubkey
      - twofa
      - basesigned
      - commitssigned

  mimetype_mapping:
    .apk: application/vnd.android.package-archive

forgejo_security:
  install_lock: false
  secret_key: ""
  secret_key_uri: file:/etc/forgejo/secret_key
  internal_token: ""
  internal_token_uri: file:/etc/forgejo/internal_token
  login_remember_days: 7
  cookie_username: forgejo_awesome
  cookie_remember_name: forgejo_incredible
  reverse_proxy:
    authentication:
      user: X-WEBAUTH-USER
      email: X-WEBAUTH-EMAIL
      full_name: X-WEBAUTH-FULLNAME
    limit: 1
    trusted_proxies:
      - 127.0.0.0/8
      - ::1/128
  min_password_length: 6
  import_local_paths: false
  disable_git_hooks: true
  disable_webhooks: false
  only_allow_push_if_forgejo_environment_set: true
  password_complexity:
    - off
  password_hash_algo: pbkdf2
  csrf_cookie_http_only: true
  password_check_pwn: false
  successful_tokens_cache_size: 20

forgejo_server:
  protocol: http
  use_proxy_protocol: false
  proxy_protocol_tls_bridging: false
  proxy_protocol_header_timeout: 5s
  proxy_protocol_accept_unknown: false
  domain: localhost
  root_url: "%(protocol)s://%(domain)s:%(HTTP_PORT)s/"
  static_url_prefix: ""
  http_addr: 0.0.0.0
  http_port: 3000
  redirect_other_port: false
  port_to_redirect: 80
  redirector_use_proxy_protocol: "%(use_proxy_pROTOCOL)s"
  ssl_min_version: tlsv1.2
  ssl_max_version: ""
  ssl_curve_preferences:
    - x25519
    - p256
  # will default to "ecdhe_ecdsa_with_aes_256_gcm_sha384,ecdhe_rsa_with_aes_256_gcm_sha384,ecdhe_ecdsa_with_aes_128_gcm_sha256,ecdhe_rsa_with_aes_128_gcm_sha256,ecdhe_ecdsa_with_chacha20_poly1305,ecdhe_rsa_with_chacha20_poly1305" if aes is supported by hardware, otherwise chacha will be first.
  ssl_cipher_suites: []
  per_write_timeout: 30s
  per_write_per_kb_timeout: 30s
  unix_socket_permission: 666
  local_root_url: "%(PROTOCOL)s://%(HTTP_ADDR)s:%(HTTP_PORT)s/"
  local_use_proxy_protocol: "%(USE_PROXY_PROTOCOL)s"
  disable_ssh: false
  start_ssh_server: false
  ssh_server_use_proxy_protocol: false
  builtin_ssh_server_user: "%(RUN_USER)s"
  ssh_domain: "%(DOMAIN)s"
  ssh_user: "%(BUILTIN_SSH_SERVER_USER)s"
  ssh_listen_host: ""
  ssh_port: 22
  ssh_listen_port: "%(SSH_PORT)s"
  ssh_root_path: ""
  ssh_create_authorized_keys_file: true
  ssh_create_authorized_principals_file: true
  ssh_server_ciphers:
    - chacha20-poly1305@openssh.com
    - aes128-ctr
    - aes192-ctr
    - aes256-ctr
    - aes128-gcm@openssh.com
    - aes256-gcm@openssh.com
  ssh_server_key_exchanges:
    - curve25519-sha256
    - ecdh-sha2-nistp256
    - ecdh-sha2-nistp384
    - ecdh-sha2-nistp521
    - diffie-hellman-group14-sha256
    - diffie-hellman-group14-sha1
  ssh_server_macs:
    - hmac-sha2-256-etm@openssh.com
    - hmac-sha2-256
    - hmac-sha1
  ssh_server_host_keys:
    - ssh/forgejo.rsa
    - ssh/gogs.rsa
  ssh_key_test_path: ""
  ssh_keygen_path: ssh-keygen
  ssh_authorized_keys_backup: true
  ssh_authorized_principals_allow:
    - email
    - username
  ssh_authorized_principals_backup: true
  ssh_trusted_user_ca_keys: []
  ssh_trusted_user_ca_keys_filename: ""
  ssh_expose_anonymous: false
  ssh_per_write_timeout: 30s
  ssh_per_write_per_kb_timeout: 30s
  minimum_key_size_check: false
  offline_mode: false
  disable_router_log: false
  enable_acme: false
  acme_url: ""
  acme_accepttos: false
  acme_ca_root: ""
  acme_email: ""
  acme_directory: https
  cert_file: https/cert.pem
  key_file: https/key.pem
  static_root_path: "" # will default to the built-in value _`StaticRootPath`_
  app_data_path: data # relative paths will be made absolute with _`AppWorkPath`_
  enable_gzip: false
  enable_pprof: false
  pprof_data_path: data/tmp/pprof # path is relative to _`AppWorkPath`_
  # landing page, can be "home", "explore", "organizations", "login", or any URL such as "/org/repo" or even "https://anotherwebsite.com"
  # the "login" choice is not a security measure but just a UI flow change, use REQUIRE_SIGNIN_VIEW to force users to log in.
  landing_page: home
  lfs_start_server: false
  lfs_jwt_secret: ""
  lfs_http_auth_expiry: 20m
  lfs_max_file_size: 0
  lfs_locks_paging_num: 50
  allow_graceful_restarts: true
  graceful_hammer_time: 60s
  startup_timeout: 0
  static_cache_time: 6h

forgejo_service:
  active_code_live_minutes: 180
  reset_passwd_code_live_minutes: 180
  register_email_confirm: false
  register_manual_confirm: false
  email_domain_whitelist: []
  email_domain_blocklist: []
  disable_registration: false
  allow_only_internal_registration: false
  allow_only_external_registration: false
  require_signin_view: false
  enable_notify_mail: false
  enable_basic_authentication: true
  enable_reverse_proxy_authentication: false
  enable_reverse_proxy_auto_registration: false
  enable_reverse_proxy_email: false
  enable_reverse_proxy_full_name: false
  enable_captcha: false
  require_captcha_for_login: false
  captcha_type: image
  recaptcha_url: https://www.google.com/recaptcha/
  recaptcha_secret: ""
  recaptcha_sitekey: ""
  hcaptcha_secret: ""
  hcaptcha_sitekey: ""
  mcaptcha_url: https://demo.mcaptcha.org
  mcaptcha_secret: ""
  mcaptcha_sitekey: ""
  cf_turnstile_sitekey: ""
  cf_turnstile_secret: ""
  default_keep_email_private: false
  default_allow_create_organization: true
  default_user_is_restricted: false
  default_user_visibility: public
  allowed_user_visibility_modes:
    - public
    - limited
    - private
  default_org_visibility: public
  default_org_member_visible: false
  default_enable_dependencies: true
  allow_cross_repository_dependencies: true
  enable_user_heatmap: true
  enable_timetracking: true
  default_enable_timetracking: true
  default_allow_only_contributors_to_track_time: true
  no_reply_address: ""
  show_registration_button: true
  show_milestones_dashboard_page: true
  auto_watch_new_repos: true
  auto_watch_on_changes: false
  user_delete_with_comments_max_time: 0
  valid_site_url_schemes:
    - http
    - https

forgejo_session:
  provider: memory
  provider_config: data/sessions
  cookie_name: i_like_forgejo
  cookie_secure: false
  gc_interval_time: 86400
  session_life_time: 86400
  same_site: lax

forgejo_ssh:
  minimum_key_sizes:
    ed25519: 256
    ecdsa: 256
    rsa: 2047
    dsa: -1

forgejo_storage:
  storage_type: local
  repo_-archive:
    storage_type: local
  packages:
    storage_type: local
  actions_log:
    storage_type: local

forgejo_task:
  queue_type: channel
  queue_length: 1000
  queue_conn_str: "redis://127.0.0.1:6379/0?pool_size=100&idle_timeout=180s"

forgejo_time:
  format: ""
  default_ui_location: ""

forgejo_ui:
  explore_paging_num: 20
  issue_paging_num: 20
  feed_max_commit_num: 5
  feed_paging_num: 20
  sitemap_paging_num: 20
  graph_max_commit_num: 100
  code_comment_lines: 4
  theme_color_meta_tag: "#6cc644"
  max_display_file_size: 8388608
  show_user_email: true
  default_theme: auto
  themes:
    - auto
    - forgejo
    - arc-green
  reactions:
    - "+1"
    - "-1"
    - laugh
    - hooray
    - confused
    - heart
    - rocket
    - eyes
  custom_emojis:
    - forgejo
    - codeberg
    - gitlab
    - git
    - github
    - gogs
  default_show_full_name: false
  search_repo_description: true
  use_service_worker: false
  only_show_relevant_repos: false
  admin:
    user_paging_num: 50
    repo_paging_num: 50
    notice_paging_num: 25
    org_paging_num: 50
  user:
    repo_paging_num: 15
  meta:
    author: forgejo - git with a cup of tea
    description: forgejo (git with a cup of tea) is a painless self-hosted Git service written in Go
    keywords:
      - go
      - git
      - self-hosted
      - forgejo
  notification:
    min_timeout: 10s
    max_timeout: 60s
    timeout_step: 10s
    event_source_update_time: 10s
  svg:
    enable_render: true
  csv:
    max_file_size: 524288

forgejo_webhook:
  queue_length: 1000
  deliver_timeout: 5
  allowed_host_list:
    - external
  skip_tls_verify: false
  paging_num: 10
  proxy_url: ""
  proxy_hosts: []

forgejo_auths:
  ldap:
    state: ""                                     # module.params.get("state")
    name: ""                                      # Authentication name.
    active: ""                                    # (de)activate the authentication source.
    security_protocol: ""                         # Security protocol name.
    skip_tls_verify: ""                           # Disable TLS verification.
    hostname: ""                                  # The address where the LDAP server can be reached.
    port: ""                                      # The port to use when connecting to the LDAP server.
    user_search_base: ""                          # The LDAP base at which user accounts will be searched for.
    filters:                                      #
      users: ""                                   # An LDAP filter declaring how to find the user record that is attempting to authenticate.
      admin: ""                                   # An LDAP filter specifying if a user should be given administrator privileges.
      restricted: ""                              # An LDAP filter specifying if a user should be given restricted status.
    allow_deactivate_all: ""                      # Allow empty search results to deactivate all users.
    attributes:                                   #
      username: ""                                # The attribute of the user’s LDAP record containing the user name.
      firstname: ""                               # The attribute of the user’s LDAP record containing the user’s first name.
      surename: ""                                # The attribute of the user’s LDAP record containing the user’s surname.
      email: ""                                   # The attribute of the user’s LDAP record containing the user’s email address.
      public_ssh_key: ""                          # The attribute of the user’s LDAP record containing the user’s public ssh key.
      avatar: ""                                  # The attribute of the user’s LDAP record containing the user’s avatar.
    skip_local_2fa: ""                            # Set to true to skip local 2fa for users authenticated by this source
    bind_dn: ""                                   # The DN to bind to the LDAP server with when searching for the user.
    bind_password: ""                             # The password for the Bind DN, if any.
    attributes_in_bind: ""                        # Fetch attributes in bind DN context.
    synchronize_users: ""                         # Enable/ Disable user synchronization.

```

## Contribution

Please read [Contribution](CONTRIBUTING.md)

## Development,  Branches (Git Tags)

The `master` Branch is my *Working Horse* includes the "latest, hot shit" and can be complete broken!

If you want to use something stable, please use a [Tagged Version](https://github.com/bodsch/ansible-forgejo/tags)!


## Author

- Bodo Schulz

## License

[Apache](LICENSE)

**FREE SOFTWARE, HELL YEAH!**



## Tools

[Tea - CLI for forgejo](https://dl.forgejo.com/tea/0.9.2/
