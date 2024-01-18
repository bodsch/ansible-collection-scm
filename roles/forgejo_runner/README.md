
# Ansible Role:  `forgejo-runner`

Ansible role to install and configure [forgejo-runner](https://code.forgejo.org/forgejo/runner) on various linux systems.

Forgejo is a self-hosted lightweight software forge.
Easy to install and low maintenance, it just does the job.


[![GitHub Workflow Status](https://img.shields.io/github/actions/workflow/status/bodsch/ansible-forgejo-runner/main.yml?branch=main)][ci]
[![GitHub issues](https://img.shields.io/github/issues/bodsch/ansible-forgejo-runner)][issues]
[![GitHub release (latest by date)](https://img.shields.io/github/v/release/bodsch/ansible-forgejo-runner)][releases]

[ci]: https://github.com/bodsch/ansible-forgejo-runner/actions
[issues]: https://github.com/bodsch/ansible-forgejo-runner/issues?q=is%3Aopen+is%3Aissue
[releases]: https://github.com/bodsch/ansible-forgejo-runner/releases


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
forgejo_runner_version: 3.3.0

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

forgejo_runner_forgejo: "localhost"

forgejo_runner_register:
  tags: []
  instance: ""
  name: "runner"
  token: ""

forgejo_runner_service: {}
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
