## queue
```yaml
forgejo_queue:
  default:
    type: ""                                      # persistable-channel
    datadir: ""                                   # queues/ # Relative paths will be made absolute against `%(APP_DATA_PATH)s`.
    length: ""                                    # 20
    batch_length: ""                              # 20
    conn_str: ""                                  # redis://127.0.0.1:6379/0
    queue_name: ""                                # "_queue"
    set_name: ""                                  # "_unique"
    max_workers: ""                               # 1-10
```
