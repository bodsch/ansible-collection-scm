## database
```yaml
forgejo_database:
  db_type: sqlite3                                # sqlite2, mysql, postgres
  # mariadb configuration
  host: ""                                        # 127.0.0.1:3306 ; can use socket e.g. /var/run/mysqld/mysqld.sock
  name: ""                                        # forgejo
  user: ""                                        # root
  passwd: ""                                      # ;use passwd: `your password` for quoting if you use special characters in the password.
  ssl_mode: ""                                    # false ; either "false" (default), "true", or "skip-verify"
  charset: ""                                     # utf8mb4 ;either "utf8" or "utf8mb4", default is "utf8mb4".
  # ; postgres configuration
  # db_type: postgres
  # host: 127.0.0.1:5432 ; can use socket e.g. /var/run/postgresql/
  # name: forgejo
  # user: root
  # passwd: ""
  # schema: ""
  # ssl_mode: disable                             # either "disable" (default), "require", or "verify-full"
  # sqlite configuration
  path: data/forgejo.db                             #
  sqlite_timeout: ""                              # query timeout defaults to: 500
  sqlite_journal_mode: ""                         # defaults to sqlite database default (often delete), can be used to enable wal mode.
  iterate_buffer_size: ""                         # 50
  log_sql: ""                                     # false
  db_retries: ""                                  # 10
  db_retry_backoff: ""                            # 3s
  max_idle_conns: ""                              # 2
  conn_max_lifetime: ""                           # 3s
  max_open_conns: ""                              # 0
  auto_migration: ""                              # true
  # changes between 1.20 and 9.0
  # - CHARSET = utf8mb4 ;either "utf8" or "utf8mb4", default is "utf8mb4".
  charset_collation: ""                           # ""; Empty as default, Gitea will try to find a case-sensitive collation. Don't change it unless you clearly know what you need.
  conn_max_idletime: ""                           # 0
  slow_query_threshold: "5s"
  slow_query_treshold: "5s"
```
