# coding: utf-8
from __future__ import annotations, unicode_literals

import pytest
from helper.molecule import get_vars, infra_hosts, local_facts

testinfra_hosts = infra_hosts(host_name="instance")

# --- tests -----------------------------------------------------------------

# _facts = local_facts(host=host, fact="forgejo-runner")


@pytest.mark.parametrize("dirs", ["/etc/forgejo-runner"])
def test_directories(host, dirs):
    d = host.file(dirs)
    assert d.is_directory


def test_forgejo_runner_files(host, get_vars):
    """ """
    distribution = host.system_info.distribution
    release = host.system_info.release

    print(f"distribution: {distribution}")
    print(f"release     : {release}")

    version = local_facts(host=host, fact="forgejo-runner").get("version")

    # version = local_facts(host).get("version")

    install_dir = get_vars.get("forgejo_runner_install_path")
    defaults_dir = get_vars.get("forgejo_runner_defaults_directory")
    config_dir = get_vars.get("forgejo_runner_config_dir")

    if "latest" in install_dir:
        install_dir = install_dir.replace("latest", version)

    files = []
    files.append("/usr/bin/forgejo-runner")

    if install_dir:
        files.append(f"{install_dir}/forgejo-runner")
    if defaults_dir and not distribution == "artix":
        files.append(f"{defaults_dir}/forgejo-runner")
    if config_dir:
        files.append(f"{config_dir}/config.yaml")

    print(files)

    for _file in files:
        f = host.file(_file)
        assert f.is_file


def test_user(host, get_vars):
    """ """
    user = get_vars.get("forgejo_runner_system_user", "forgejo")
    group = get_vars.get("forgejo_runner_system_group", "forgejo")

    assert host.group(group).exists
    assert host.user(user).exists
    assert group in host.user(user).groups
    assert host.user(user).home == "/var/lib/forgejo-runner"


def test_service(host, get_vars):
    service = host.service("forgejo-runner")
    assert service.is_enabled
    assert service.is_running
