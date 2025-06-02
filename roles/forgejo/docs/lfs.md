## lfs
```yaml
forgejo_lfs:
  storage_type: "local"                           # local, minio
  path: ""                                        # data/lfs
  minio_base_path: ""
  # minio_endpoint: ""
  # minio_access_key_id: ""
  # minio_secret_access_key: ""
  # minio_bucket: ""
  # minio_location: ""
  # minio_use_ssl: ""
  # minio_insecure_skip_verify: ""
  # minio_checksum_algorithm: ""
  client:
    batch_size: ""                                # 20
    batch_operation_concurrency: ""               # 8
```
