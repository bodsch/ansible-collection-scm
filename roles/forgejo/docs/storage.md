## storage
```yaml
forgejo_storage:
  storage_type: ""                                # local, minio
  repo_archive:
    storage_type: ""                              # local
  packages:
    storage_type: ""                              # local
  actions_log:
    storage_type: ""                              # local
  actions_artifacts:
    storage_type: ""                              # local
  minio: []
  #   - name: my_minio
  #     storage_type: minio
  #     endpoint: localhost:9000
  #     access_key_id: ""
  #     secret_access_key: ""
  #     bucket: gitea
  #     bucket_lookup: ""
  #     location: us-east-1
  #     use_ssl: false
  #     insecure_skip_verify: false
  #     checksum_algorithm: ""
```
