
# Ansible Role:  `bodsch.scm.forgejo_runner`

Ansible role to install and configure [forgejo-runner](https://code.forgejo.org/forgejo/runner) on various linux systems.

Forgejo is a self-hosted lightweight software forge.
Easy to install and low maintenance, it just does the job.


## Requirements & Dependencies


### Operating systems

Tested on

* Arch Linux
* Debian based
    - Debian 10 / 11 / 12
    - Ubuntu 20.04 / 22.04

## usage

Full example

```yaml
forgejo_runner_version: 3.4.1

forgejo_runner_system_user: forgejo
forgejo_runner_system_group: forgejo
forgejo_runner_config_dir: /etc/forgejo-runner
forgejo_runner_working_dir: /var/lib/forgejo-runner
forgejo_runner_home_dir: /home/{{ forgejo_runner_system_user }}

forgejo_runner_systemd:
  unit:
    after:
      - syslog.target
      - network.target
    wants: []
    requires: []

forgejo_runner_release: {}

forgejo_runner_direct_download: false

forgejo_runner_controller:
  hostname: "localhost"
  username: "forgejo"
  # groupname: "forgejo"

forgejo_runner_register:
  - name: "{{ ansible_hostname }}" # runner name
    state: disabled
    # tags: []                     #
    instance: "http://forgejo.tld" #
    secret: "" # the secret the runner will use to connect as a 40 character hexadecimal string
    scope: ""                    # {owner}[/{repo}] - leave empty for a global runner
    labels: []                   # list of labels supported by the runner (e.g. docker,ubuntu-latest,self-hosted)  (not required since v1.21)


forgejo_runner_groups: []

forgejo_runner_config:
  log:
    # trace, debug, info, warn, error, fatal
    level: info
  runner:
    file: .runner
    capacity: 1
    envs: {}
    env_file: .env
    timeout: 3h
    shutdown_timeout: 3h
    insecure: false
    fetch_timeout: 5s
    fetch_interval: 2s
    report_interval: 1s
    labels: []
  cache:
    enabled: true
    dir: ""
    host: ""
    port: 0
    external_server: ""
  container:
    network: ""
    enable_ipv6: false
    privileged: false
    options:
    workdir_parent:
    valid_volumes: []
    docker_host: "-"
    force_pull: false
  host:
    workdir_parent: ""
```

### `forgejo_runner_controller`

Defines the forgejo host to which the Runner is to be connected.

```yaml
forgejo_runner_controller:
  hostname: "forgejo.molecule.lan"
  username: "forgejo"
```

### `forgejo_runner_register`

Defines the runner with its configuration.  
`secret` must be a 42-character hex string! 

```yaml
forgejo_runner_register:
  - name: "{{ ansible_hostname }}"
    tags: []
    instance: "http://forgejo.molecule.lan"
    secret: "4ef3eb262c04aad5e279511c1c86f7377e28d6b9"
    scope: ""
    labels:
      - ubuntu-latest
      - ubuntu-22.04
```

### `forgejo_runner_config`

The Runner configuration.  
Various parameters can be defined here that the runner requires at runtime.

This configuration is required for its start.

The `labels` to which the runner reacts when an action is triggered are also defined here.

```yaml
forgejo_runner_config:
  log:
    # trace, debug, info, warn, error, fatal
    level: info
  runner:
    file: .runner
    capacity: 2
    envs: {}
    env_file: .env
    timeout: 3h
    insecure: true
    fetch_timeout: 5s
    fetch_interval: 2s
    labels:
      - label: ubuntu-latest
        type: docker
        container: docker.io/ubuntu:latest
      - label: ubuntu-22.04
        type: docker
        container: docker.io/ubuntu:22.04
      - label: lxc
        type: lxc
        container: debian:bullseye
      - label: self-hosted
        type: host
        container: "-self-hosted"
```

## Contribution

Please read [Contribution](CONTRIBUTING.md)

## Development,  Branches (Git Tags)

The `master` Branch is my *Working Horse* includes the "latest, hot shit" and can be complete broken!

If you want to use something stable, please use a [Tagged Version](https://github.com/bodsch/ansible-forgejo-runner/tags)!


## Author

- Bodo Schulz

## License

[Apache](LICENSE)

**FREE SOFTWARE, HELL YEAH!**
