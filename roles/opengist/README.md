# `bodsch.scm.opengist`

Ansible role to install and configure [opengist](https://github.com/thomiceli/opengist).

Opengist is an self-hosted pastebin powered by Git.
A Open-Source alternative to Github Gist.


## Requirements & Dependencies


### Operating systems

Tested on

* Arch Linux
* Debian based
    - Debian 10 / 11 / 12
    - Ubuntu 20.04 / 22.04

## usage

```yaml
opengist_config:
  log_level: info
  log_output:
    - stdout
    - file
  external_url: ""
  opengist_home: ""
  secrect_key: ""
  db_uri: ""
  index:
    type: bleve
    meili:
      host: ""
      api_key: ""
  git:
    default_branch: ""

  sqlite:
    journal_mode: WAL

  http:
    host: "127.0.0.1"
    port: 6157
    git_enabled: true

  unix_socket_pemissions: "0666"

  metrics:
    enabled: false

  ssh:
    host: "127.0.0.1"
    port: 2222
    git_enabled: false
    external_domain: ""
    keygen_executable: "ssh-keygen"

  github:
    client_key: ""
    secret: ""

  gitlab:
    client_key: ""
    secret: ""
    # URL of the Gitlab instance. Default: https://gitlab.com/
    url: https://gitlab.com/
    # The name of the GitLab instance. It is displayed in the OAuth login button. Default: GitLab
    name: GitLab

  gitea:
    client_key: ""
    secret: ""
    # URL of the Gitea instance. Default: https://gitea.com/
    url: https://gitea.com/
    # The name of the Gitea instance. It is displayed in the OAuth login button. Default: Gitea
    name: Gitea

  oidc:
    provider_name: ""
    client_key: ""
    secret: ""
    # Discovery endpoint of the OpenID provider. Generally something like http://auth.example.com/.well-known/openid-configuration
    discovery_url: ""
    # The name of the claim containing the groups
    group_claim_name: ""
    # The name of the group that should receive admin rights
    admin_group: ""

  ldap:
    url:
    # Bind DN to authenticate against the LDAP e.g: cn=read-only-admin,dc=example,dc=com
    bind_dn: ""
    # The password for the Bind DN.
    bind_credentials: ""
    # The Base DN to start search from e.g: ou=People,dc=example,dc=com
    search_base: ""
    # The filter to search against (the format string %s will be replaced with the username) e.g: (uid=%s)
    search_filter: ""

  custom:
    name: ""
    logo: ""
    favicon: ""
    static_links: []
    #  - name: Gitea
    #    path: https://gitea.com
    #  - name: forgejo
    #    path: https://forgejo.com
    #  - name: Legal notices
    #    path: legal.html
```

---

## Author

- Bodo Schulz

**FREE SOFTWARE, HELL YEAH!**
