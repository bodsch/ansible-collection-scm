## federation
```yaml
forgejo_federation:
  enabled: ""                                     # false
  share_user_statistics: ""                       # true
  max_size: ""                                    # 4
  algorithms: []                                  # [rsa-sha256, rsa-sha512, ed25519]
  digest_algorithm: ""                            # SHA-256
  get_headers: []                                 # ["(request-target)", Date]
  post_headers: []                                # ["(request-target)", Date, Digest]
```
