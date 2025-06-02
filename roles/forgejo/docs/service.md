## service
```yaml
forgejo_service:
  active_code_live_minutes: ""                    # 180
  reset_passwd_code_live_minutes: ""              # 180
  register_email_confirm: ""                      # false
  register_manual_confirm: ""                     # false
  email_domain_whitelist: []
  email_domain_blocklist: []
  disable_registration: ""                        # false
  allow_only_internal_registration: ""            # false
  allow_only_external_registration: ""            # false
  require_signin_view: ""                         # false
  enable_notify_mail: ""                          # false
  enable_basic_authentication: ""                 # true
  enable_reverse_proxy_authentication: ""         # false
  enable_reverse_proxy_auto_registration: ""      # false
  enable_reverse_proxy_email: ""                  # false
  enable_reverse_proxy_full_name: ""              # false
  enable_captcha: ""                              # false
  require_captcha_for_login: ""                   # false
  require_external_registration_captcha: ""       # false
  require_external_registration_password: ""       # false
  captcha_type: ""                                # image
  recaptcha_url: ""                               # https://www.google.com/recaptcha/
  recaptcha_secret: ""
  recaptcha_sitekey: ""
  hcaptcha_secret: ""
  hcaptcha_sitekey: ""
  mcaptcha_url: ""                                # https://demo.mcaptcha.org
  mcaptcha_secret: ""
  mcaptcha_sitekey: ""
  cf_turnstile_sitekey: ""
  cf_turnstile_secret: ""
  default_keep_email_private: ""                  # false
  default_allow_create_organization: ""           # true
  default_user_is_restricted: ""                  # false
  default_user_visibility: ""                     # public
  allowed_user_visibility_modes: []               # [public, limited, private]
  default_org_visibility: ""                      # public
  default_org_member_visible: ""                  # false
  default_enable_dependencies: ""                 # true
  allow_cross_repository_dependencies: ""         # true
  enable_user_heatmap: ""                         # true
  enable_timetracking: ""                         # true
  default_enable_timetracking: ""                 # true
  default_allow_only_contributors_to_track_time: "" # true
  no_reply_address: ""
  show_registration_button: ""                    # true
  show_milestones_dashboard_page: ""              # true
  auto_watch_new_repos: ""                        # true
  auto_watch_on_changes: ""                       # false
  user_delete_with_comments_max_time: ""          # 0
  valid_site_url_schemes: []                      # [http, https]
  # added in version 1.20
  domain_endpoint: "release.forgejo.org"
  # changes between 1.20 and 9.0
  allow_dots_in_usernames: true
  enable_reverse_proxy_authentication_api: false
  user_location_map_url: https://www.openstreetmap.org/search?query=
  # changes between 10.0.0 and 10.0.3
  explore:
    require_signin_view: false
    disable_users_page: false
    disable_organizations_page: false
    disable_code_page: false
```
