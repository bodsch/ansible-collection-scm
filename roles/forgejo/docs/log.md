## log
```yaml
forgejo_log:
  root_path: ""
  mode:                                           # [console, file]
    - console
  level: info                                     # info   | Either "Trace", "Debug", "Info", "Warn", "Error" or "None", default is "Info"
  disable_router_log: ""                          # false
  router: ""                                      # console
  enable_access_log: ""                           # false
  access: ""                                      # file
  # TODO
  access_log_template: !unsafe ""
    # {{.Ctx.RemoteAddr}} - {{.Identity}}
    # {{.Start.Format "[02/Jan/2006:15:04:05 -0700]" }}
    # {{.Ctx.Req.Method}}
    # {{.Ctx.Req.URL.RequestURI}}
    # {{.Ctx.Req.Proto}}"
    # {{.ResponseWriter.Status}}
    # {{.ResponseWriter.Size}}
    # \"{{.Ctx.Req.Referer}}\" \"{{.Ctx.Req.UserAgent}}\"
  enable_ssh_log: ""                              # false
  stacktrace_level: ""                            # none
  buffer_len: ""                                  # 10000
  request_id_headers: []
  #   - X-Request-ID
  #   - X-Trace-ID
  #   - X-Req-ID

  log_writer:
    # https://forgejo.org/docs/latest/admin/logging-documentation
    - name: console                                 # standard console
      mode: console                                 #
      level: info                                   #
      flags: stdflags                               #
      colorize: false                               #
    # - name: file                                    #
    #   level: ""                                     #
    #   file_name: ""                                 #
    #   log_rotate: ""                                # true
    #   max_size_shift: ""                            # 28
    #   daily_rotate: ""                              # true
    #   max_days: ""                                  # 7
    #   compress: ""                                  # true
    #   compression_level: ""                         # -1
    # - name: conn
    #   level: ""
    #   reconnect_on_msg: ""                          # false
    #   reconnect: ""                                 # false
    #   protocol: ""                                  # tcp (either "tcp", "unix" or "udp")
```
