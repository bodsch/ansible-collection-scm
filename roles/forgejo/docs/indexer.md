## indexer
```yaml
forgejo_indexer:
  issue_indexer_type: ""                          # bleve (currently support: bleve, db, elasticsearch or meilisearch)
  issue_indexer_path: ""                          # indexers/issues.bleve
  issue_indexer_conn_str: ""                      # http://elastic:changeme@localhost:9200
  issue_indexer_name: ""                          # forgejo_issues
  startup_timeout: ""                             # 30s
  # ; **DEPRECATED** use settings in `[queue.issue_indexer]`.
  issue_indexer_queue_type: ""                    # levelqueue (currently support: channel, levelqueue or redis)
  # ; **DEPRECATED** use settings in `[queue.issue_indexer]`
  issue_indexer_queue_dir: ""                     # queues/common
  # ; **DEPRECATED** use settings in `[queue.issue_indexer]`.
  issue_indexer_queue_conn_str: ""                # "addrs=127.0.0.1:6379 db=0"
  # ; **DEPRECATED** use settings in `[queue.issue_indexer]`.
  issue_indexer_queue_batch_number: ""            # 20
  repo_indexer_enabled: ""                        # false
  # changes between 1.20 and 9.0
  # repo indexer units, the items to index, could be `sources`, `forks`, `mirrors`, `templates` or any combination of them separated by a comma.
  # If empty then it defaults to `sources` only, as if you'd like to disable fully please see REPO_INDEXER_ENABLED.
  repo_indexer_repo_types:
    - sources
    - forks
    - mirrors
    - templates
  repo_indexer_type: ""                           # bleve
  repo_indexer_path: ""                           # indexers/repos.bleve
  repo_indexer_conn_str: ""
  repo_indexer_name: ""                           # forgejo_codes
  repo_indexer_include: []
  repo_indexer_exclude: []
  # **DEPRECATED** use settings in `[queue.issue_indexer]`.
  update_buffer_len: ""                           # 20
  max_file_size: ""                               # 1048576
  repo_indexer_exclude_vendored: ""               # true
```
