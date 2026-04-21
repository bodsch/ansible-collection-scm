# coding: utf-8
from __future__ import annotations, unicode_literals

import pytest
from helper.molecule import get_vars, infra_hosts, local_facts

testinfra_hosts = infra_hosts(host_name="all")

# --- tests -----------------------------------------------------------------

# _facts = local_facts(host=host, fact="forgejo")


@pytest.mark.parametrize("dirs", ["/etc/forgejo"])
def test_directories(host, dirs):
    d = host.file(dirs)
    assert d.is_directory


def test_forgejo_files(host, get_vars):
    """ """
    distribution = host.system_info.distribution
    release = host.system_info.release
    version = local_facts(host=host, fact="forgejo").get("version")

    print(f"distribution: {distribution}")
    print(f"release     : {release}")
    print(f"version     : {version}")

    install_dir = get_vars.get("forgejo_install_path")
    defaults_dir = get_vars.get("forgejo_defaults_directory")
    config_dir = get_vars.get("forgejo_config_dir")

    if "{{ forgejo_version }}" in install_dir:
        install_dir = install_dir.replace("{{ forgejo_version }}", version)

    if "latest" in install_dir:
        install_dir = install_dir.replace("latest", version)

    files = []
    files.append("/usr/bin/forgejo")

    if install_dir:
        files.append(f"{install_dir}/forgejo")
    if defaults_dir and not distribution == "artix":
        files.append(f"{defaults_dir}/forgejo")
    if config_dir:
        files.append(f"{config_dir}/forgejo.ini")

    print(files)

    for _file in files:
        f = host.file(_file)
        assert f.is_file


def test_user(host, get_vars):
    """ """
    user = get_vars.get("forgejo_system_user", "forgejo")
    group = get_vars.get("forgejo_system_group", "forgejo")

    assert host.group(group).exists
    assert host.user(user).exists
    assert group in host.user(user).groups
    assert host.user(user).home == "/var/lib/forgejo"


def test_service(host, get_vars):
    service = host.service("forgejo")
    assert service.is_enabled
    assert service.is_running


def test_open_port(host, get_vars):
    for i in host.socket.get_listening_sockets():
        print(i)

    forgejo_server = get_vars.get("forgejo_server", {})

    print(forgejo_server)

    if isinstance(forgejo_server, dict):
        forgejo_web = forgejo_server.get("web", {})

        addr = forgejo_web.get("http_addr", "0.0.0.0")
        port = forgejo_web.get("http_port", "3000")

        listen_address = f"{addr}:{port}"
    else:
        listen_address = "0.0.0.0:3000"

    service = host.socket(f"tcp://{listen_address}")
    assert service.is_listening
