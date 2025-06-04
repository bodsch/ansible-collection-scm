## cache
```yaml
forgejo_cache:
  enabled: ""                                     # true
  adapter: ""                                     # memory ("memory", "redis", "memcache", or "twoqueue")
  interval: ""                                    # 60
  # for "redis" and "memcache", connection host address
  #   - redis: `redis://127.0.0.1:6379/0?pool_size=100&idle_timeout=180s`
  #   - memcache: `127.0.0.1:11211`
  #   - twoqueue: `{"size":50000,"recent_ratio":0.25,"ghost_ratio":0.5}` or `50000`
  host: ""
  item_ttl: ""                                    # 16h
  last_commit:
    enabled: ""                                   # true
    item_ttl: ""                                  # 8760h
    commits_count: ""                             # 1000
```
