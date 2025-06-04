## attachment
```yaml
forgejo_attachment:
  enabled: ""                                     # true
  # list of allowed file extensions (`.zip`),
  # mime types (`text/plain`) or
  # wildcard type (`image/*`, `audio/*`, `video/*`).
  # Empty value or `*/*` allows all types.
  allowed_types: []                               # []
  max_size: ""                                    # 4
  max_files: ""                                   # 5
  storage_type: ""                                # local
  serve_direct: ""                                # false
  path: ""                                        # data/attachments
  minio:
    endpoint: ""                                  # localhost:9000
    access_key_id: ""
    secret_access_key: ""
    bucket: ""                                    # forgejo
    bucket_lookup: ""                             # auto, dns, path
    location: ""                                  # us-east-1
    base_path: ""                                 # attachments/
    use_ssl: ""                                   # false
    insecure_skip_verify: ""                      # false
    checksum_algorithm: ""                        # default
```
