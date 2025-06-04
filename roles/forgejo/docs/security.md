## security
```yaml
forgejo_security:
  install_lock: true                              # false
  secret_key: ""
  secret_key_uri: ""                              # file:/etc/forgejo/secret_key
  internal_token: ""
  internal_token_uri: ""                          # file:/etc/forgejo/internal_token
  login_remember_days: ""                         # 7
  cookie_username: ""                             # forgejo_awesome
  cookie_remember_name: ""                        # forgejo_incredible
  reverse_proxy:
    authentication:
      user: ""                                    # X-WEBAUTH-USER
      email: ""                                   # X-WEBAUTH-EMAIL
      full_name: ""                               # X-WEBAUTH-FULLNAME
    limit: ""                                     # 1
    trusted_proxies: []                           # [127.0.0.0/8, ::1/128]
  min_password_length: ""                         # 6
  import_local_paths: ""                          # false
  disable_git_hooks: ""                           # true
  disable_webhooks: ""                            # false
  only_allow_push_if_forgejo_environment_set: ""    # true
  password_complexity: []                         # [off]
  password_hash_algo: ""                          # pbkdf2
  csrf_cookie_http_only: ""                       # true
  password_check_pwn: ""                          # false
  successful_tokens_cache_size: ""                # 20
  # changes between 1.20 and 9.0
  disable_query_auth_token: ""                    # false
```
