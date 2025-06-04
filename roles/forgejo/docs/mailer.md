## mailer
```yaml
forgejo_mailer:
  enabled: ""                                     # false
  send_buffer_len: ""                             # 100
  subject_prefix: ""
  protocol: ""                                    # one of "smtp", "smtps", "smtp+starttls", "smtp+unix", "sendmail", "dummy"
  smtp_addr: ""
  smtp_port: ""                                   # 25:  insecure smtp / 465: smtp secure / 587: starttls
  enable_helo: ""                                 # true
  helo_hostname: ""
  force_trust_server_cert: ""                     # false
  use_client_cert: ""                             # false
  client_cert_file: ""                            # custom/mailer/cert.pem
  client_key_file: ""                             # custom/mailer/key.pem
  from: ""
  envelope_from: ""
  user: ""
  passwd: ""
  send_as_plain_text: ""                          # false
  sendmail_path: ""                               # sendmail
  sendmail_args: ""
  sendmail_timeout: ""                            # 5m
  sendmail_convert_crlf: ""                       # true
  from_display_name_format: !unsafe "{{ .DisplayName }}" # Available Variables: `.DisplayName`, `.AppName` and `.Domain`.
  override_header:
    reply_to:
      - test@example.com
      - test2@example.com
    content_type:
      - text/html
      - charset=utf-8
    in_reply_to: []
```
