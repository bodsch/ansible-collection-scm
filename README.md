# Ansible Collection - bodsch.scm


This collection aims to provide a set of small Ansible modules and helper functions.

## Included content

### Modules

| Name                      | Description |
|:--------------------------|:----|
| [github_checksum](./plugins/modules/github_checksum.py) | read a defined checksumfile and return the checksum for an artefact | 
| [github_latest](./plugins/modules/github_latest.py)     | detect the latest release or tag from GitHub | 

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
    project: prometheus
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
