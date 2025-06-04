## packages
```yaml
forgejo_packages:
  enabled: ""                                     # true
  # storage_type: "local"                           # local, minio
  # minio_base_path: ""
  chunked_upload_path: ""                         # tmp/package-upload
  limit_total_owner_count: ""                     # -1 (`-1` means no limits)
  limit_total_owner_size: ""                      # -1 (`-1` means no limits, format `1000`, `1 MB`, `1 GiB`)
  limit_size_cargo: ""                            # -1
  limit_size_chef: ""                             # -1
  limit_size_composer: ""                         # -1
  limit_size_conan: ""                            # -1
  limit_size_conda: ""                            # -1
  limit_size_container: ""                        # -1
  limit_size_generic: ""                          # -1
  limit_size_helm: ""                             # -1
  limit_size_maven: ""                            # -1
  limit_size_npm: ""                              # -1
  limit_size_nuget: ""                            # -1
  limit_size_pub: ""                              # -1
  limit_size_pypi: ""                             # -1
  limit_size_rubygems: ""                         # -1
  limit_size_swift: ""                            # -1
  limit_size_vagrant: ""                          # -1
  # path: ""                                        # data/packages
  # minio_endpoint: ""
  # minio_access_key_id: ""
  # minio_secret_access_key: ""
  # minio_bucket: ""
  # minio_location: ""
  # minio_use_ssl: ""
  # minio_insecure_skip_verify: ""
  # minio_checksum_algorithm: ""
  default_rpm_sign_enabled: ""                    # false
```
