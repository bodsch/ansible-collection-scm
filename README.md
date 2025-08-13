# Ansible Collection - bodsch.scm


This collection aims to provide a set of small Ansible modules and helper functions.


[![GitHub Workflow Status](https://img.shields.io/github/actions/workflow/status/bodsch/ansible-collection-scm/main.yml?branch=main)][ci]
[![GitHub issues](https://img.shields.io/github/issues/bodsch/ansible-collection-scm)][issues]
[![GitHub release (latest by date)](https://img.shields.io/github/v/release/bodsch/ansible-collection-scm)][releases]

[ci]: https://github.com/bodsch/ansible-collection-scm/actions
[issues]: https://github.com/bodsch/ansible-collection-scm/issues?q=is%3Aopen+is%3Aissue
[releases]: https://github.com/bodsch/ansible-collection-scm/releases


## supported operating systems

* Arch Linux
* Debian based
    - Debian 11 / 12
    - Ubuntu 22.04


## Requirements & Dependencies

- `python-dateutil`

```bash
pip install python-dateutil
```


## Contribution

Please read [Contribution](CONTRIBUTING.md)

## Development,  Branches (Git Tags)

The `master` Branch is my *Working Horse* includes the "latest, hot shit" and can be complete broken!

If you want to use something stable, please use a [Tagged Version](https://github.com/bodsch/ansible-collection-scm/tags)!

---

## Roles

| Role                                                           | Build State | Description |
|:-------------------------------------------------------------- | :---- | :---- |
| [bodsch.scm.forgejo](./roles/forgejo/README.md)                | [![GitHub Workflow Status](https://img.shields.io/github/actions/workflow/status/bodsch/ansible-collection-scm/forgejo.yml?branch=main)][workflow-forgejo] | Ansible role to install and configure [forgejo](https://forgejo.org/). |
| [bodsch.scm.forgejo_runner](./roles/forgejo_runner/README.md)  | [![GitHub Workflow Status](https://img.shields.io/github/actions/workflow/status/bodsch/ansible-collection-scm/forgejo-runner.yml?branch=main)][workflow-forgejo_runner] | Ansible role to install and configure [forgejo-runner](https://code.forgejo.org/forgejo/runner) |
| [bodsch.scm.opengist](./roles/opengist/README.md)              | [![GitHub Workflow Status](https://img.shields.io/github/actions/workflow/status/bodsch/ansible-collection-scm/opengist?branch=main)][workflow-opengist] | Ansible role to install and configure [opengist](https://github.com/thomiceli/opengist) |

[workflow-forgejo]: https://github.com/bodsch/ansible-collection-scm/actions/workflows/forgejo.yml
[workflow-forgejo_runner]: https://github.com/bodsch/ansible-collection-scm/actions/workflows/forgejo-runner.yml
[workflow-opengist]: https://github.com/bodsch/ansible-collection-scm/actions/workflows/opengist.yml


## Included content

### Modules

| Name                      | Description |
|:--------------------------|:----|
| [bodsch.scm.github_checksum](./plugins/modules/github_checksum.py) | read a defined checksumfile and return the checksum for an artefact | 
| [bodsch.scm.github_latest](./plugins/modules/github_latest.py)     | detect the latest release or tag from GitHub | 
| [bodsch.scm.github_releases](./plugins/modules/github_releases.py) | Fetches the releases version of a GitHub project and returns the download urls | 
| [bodsch.scm.forgejo](./plugins/modules/forgejo.py)                 | not used | 
| [bodsch.scm.forgejo_auth](./plugins/modules/forgejo_auth.py)       | forgejo admin auth - Modify external auth providers | 
| [bodsch.scm.forgejo_cli](./plugins/modules/forgejo_cli.py)         | wrapper to create runner token | 
| [bodsch.scm.forgejo_migrate](./plugins/modules/forgejo_migrate.py) | not used | 
| [bodsch.scm.forgejo_runner](./plugins/modules/forgejo_runner.py)   | append runner to forgejo | 
| [bodsch.scm.forgejo_user](./plugins/modules/forgejo_user.py)       | create forgejo admin user | 

## Installing this collection

You can install the memsource collection with the Ansible Galaxy CLI:

```sh
#> ansible-galaxy collection install bodsch.scm
```

To install directly from GitHub:

```sh
#> ansible-galaxy collection install git@github.com:bodsch/ansible-collection-scm.git
```


You can also include it in a `requirements.yml` file and install it with `ansible-galaxy collection install -r requirements.yml`, using the format:

```yaml
---
collections:
  - name: bodsch.scm
```

The python module dependencies are not installed by `ansible-galaxy`.  They can
be manually installed using pip:

```sh
#> pip install -r requirements.txt
```

## Using this collection


You can either call modules by their Fully Qualified Collection Namespace (FQCN), such as `bodsch.scm.github_latest`, 
or you can call modules by their short name if you list the `bodsch.scm` collection in the playbook's `collections` keyword:

```yaml
---
- name: get latest release
  delegate_to: localhost
  become: false
  run_once: true
  bodsch.scm.github_latest:
    project: scm
    repository: alertmanager
    user: "{{ lookup('env', 'GH_USER') | default(omit) }}"
    password: "{{ lookup('env', 'GH_TOKEN') | default(omit) }}"
  register: _latest_release
```


## Contribution

Please read [Contribution](CONTRIBUTING.md)

## Development,  Branches (Git Tags)

The `master` Branch is my *Working Horse* includes the "latest, hot shit" and can be complete broken!

If you want to use something stable, please use a [Tagged Version](https://github.com/bodsch/ansible-collection-scm/tags)!


## Author

- Bodo Schulz

## License

[Apache](LICENSE)

**FREE SOFTWARE, HELL YEAH!**
