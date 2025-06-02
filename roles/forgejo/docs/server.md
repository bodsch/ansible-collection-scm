## server
```yaml
forgejo_server:
  protocol: ""                                    # http
  use_proxy_protocol: ""                          # false
  proxy_protocol_tls_bridging: ""                 # false
  proxy_protocol_header_timeout: ""               # 5s
  proxy_protocol_accept_unknown: ""               # false
  domain: ""                                      # localhost
  root_url: ""                                    # "%(protocol)s://%(domain)s:%(HTTP_PORT)s/"
  static_url_prefix: ""
  http_addr: ""                                   # 0.0.0.0
  http_port: ""                                   # 3000
  redirect_other_port: ""                         # false
  port_to_redirect: ""                            # 80
  redirector_use_proxy_protocol: ""               # "%(use_proxy_pROTOCOL)s"
  ssl_min_version: ""                             # tlsv1.2
  ssl_max_version: ""
  ssl_curve_preferences: []                       # [x25519, p256]
  # will default to
  #     "ecdhe_ecdsa_with_aes_256_gcm_sha384,ecdhe_rsa_with_aes_256_gcm_sha384,ecdhe_ecdsa_with_aes_128_gcm_sha256,
  #      ecdhe_rsa_with_aes_128_gcm_sha256,ecdhe_ecdsa_with_chacha20_poly1305,ecdhe_rsa_with_chacha20_poly1305"
  # if aes is supported by hardware, otherwise chacha will be first.
  ssl_cipher_suites: []
  per_write_timeout: ""                           # 30s
  per_write_per_kb_timeout: ""                    # 30s
  unix_socket_permission: ""                      # 666
  local_root_url: ""                              # "%(PROTOCOL)s://%(HTTP_ADDR)s:%(HTTP_PORT)s/"
  local_use_proxy_protocol: ""                    # "%(USE_PROXY_PROTOCOL)s"
  disable_ssh: ""                                 # false
  start_ssh_server: ""                            # false
  ssh_server_use_proxy_protocol: ""               # false
  builtin_ssh_server_user: ""                     # "%(RUN_USER)s"
  ssh_domain: ""                                  # "%(DOMAIN)s"
  ssh_user: ""                                    # "%(BUILTIN_SSH_SERVER_USER)s"
  ssh_listen_host: ""
  ssh_port: ""                                    # 22
  ssh_listen_port: ""                             # "%(SSH_PORT)s"
  ssh_root_path: ""
  ssh_create_authorized_keys_file: ""             # true
  ssh_create_authorized_principals_file: ""       # true
  ssh_server_ciphers: []                          # [chacha20-poly1305@openssh.com, aes128-ctr, aes192-ctr, aes256-ctr, aes128-gcm@openssh.com, aes256-gcm@openssh.com]
  ssh_server_key_exchanges: []                    # [curve25519-sha256, ecdh-sha2-nistp256, ecdh-sha2-nistp384, ecdh-sha2-nistp521, diffie-hellman-group14-sha256, diffie-hellman-group14-sha1]
  ssh_server_macs: []                             # [hmac-sha2-256-etm@openssh.com, hmac-sha2-256, hmac-sha1]
  ssh_server_host_keys: []                        # [ssh/forgejo.rsa, ssh/gogs.rsa]
  ssh_key_test_path: ""
  ssh_keygen_path: ""                             # ssh-keygen
  ssh_authorized_keys_backup: ""                  # true
  ssh_authorized_principals_allow: []             # [email, username]
  ssh_authorized_principals_backup: ""            # true
  ssh_trusted_user_ca_keys: []
  ssh_trusted_user_ca_keys_filename: ""
  ssh_expose_anonymous: ""                        # false
  ssh_per_write_timeout: ""                       # 30s
  ssh_per_write_per_kb_timeout: ""                # 30s
  minimum_key_size_check: ""                      # false
  offline_mode: ""                                # false
  disable_router_log: ""                          # false
  enable_acme: ""                                 # false
  acme_url: ""
  acme_accepttos: ""                              # false
  acme_ca_root: ""
  acme_email: ""
  acme_directory: ""                              # https
  cert_file: ""                                   # https/cert.pem
  key_file: ""                                    # https/key.pem
  static_root_path: ""
  app_data_path: ""                               # data
  enable_gzip: ""                                 # false
  enable_pprof: ""                                # false
  pprof_data_path: ""                             # data/tmp/pprof
  landing_page: ""                                # home  (can be "home", "explore", "organizations", "login", or any URL such as "/org/repo" or even "https://anotherwebsite.com")
  lfs_start_server: ""                            # false
  lfs_jwt_secret: ""
  lfs_http_auth_expiry: ""                        # 20m
  lfs_max_file_size: ""                           # 0
  lfs_locks_paging_num: ""                        # 50
  allow_graceful_restarts: ""                     # true
  graceful_hammer_time: ""                        # 60s
  startup_timeout: ""                             # 0
  static_cache_time: ""                           # 6h
  # changes between 1.20 and 9.0
  lfs_jwt_secret_uri: ""                          # file:/etc/gitea/lfs_jwt_secret
  ssh_authorized_keys_command_template: ""        # !unsafe "{{.AppPath}} --config={{.CustomConf}} serv key-{{.Key.ID}}"
  # changes between v9 and v10
  lfs_max_batch_size: ""                          # 0
```
