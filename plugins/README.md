# Collections Plugins Directory

Cache Path: `$HOME/.ansible/cache/github/${project}/${repository}`

## modules

### github_latest

```
- name: get latest release
  delegate_to: localhost
  become: false
  run_once: true
  github_latest:
    project: prometheus
    repository: alertmanager
    user: "{{ lookup('env', 'GH_USER') | default(omit) }}"
    password: "{{ lookup('env', 'GH_TOKEN') | default(omit) }}"
  register: _latest_release
```

### github_checksum

```
- name: checksum
  become: false
  delegate_to: localhost
  run_once: true
  block:
    - name: get checksum list
      github_checksum:
        project: prometheus
        repository: alertmanager
        checksum_file: sha256sums.txt
        user: "{{ lookup('env', 'GH_USER') | default(omit) }}"
        password: "{{ lookup('env', 'GH_TOKEN') | default(omit) }}"
        architecture: "{{ ansible_architecture }}"
        system: "{{ ansible_facts.system }}"
        version: "{{ alertmanager_version }}"
      register: _latest_checksum
```
