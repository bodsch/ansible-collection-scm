## oauth2
```yaml
forgejo_oauth2:
  enabled: ""                                     # true
  jwt_signing_algorithm: ""                       # RS256 (Valid values: HS256, HS384, HS512, RS256, RS384, RS512, ES256, ES384, ES512, EdDSA)
  jwt_signing_private_key_file: ""                # jwt/private.pem
  jwt_secret: ""                                  #
  access_token_expiration_time: ""                # 3600
  refresh_token_expiration_time: ""               # 730
  invalidate_refresh_tokens: ""                   # false
  max_token_length: ""                            # 32767
  # changes between 1.20 and 9.0
  default_applications:
    - git-credential-oauth
    - git-credential-manager
    - tea
  jwt_secret_uri: ""                              # file:/etc/gitea/oauth2_jwt_secret
```
