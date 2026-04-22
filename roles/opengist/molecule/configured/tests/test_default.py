# coding: utf-8
from __future__ import annotations, unicode_literals

import pytest
from helper.molecule import get_vars, infra_hosts, local_facts

testinfra_hosts = infra_hosts(host_name="instance")

# --- tests -----------------------------------------------------------------

# _facts = local_facts(host=host, fact="opengist")


@pytest.mark.parametrize(
    "dirs",
    [
        "/etc/opengist",
    ],
)
def test_directories(host, dirs):
    d = host.file(dirs)
    assert d.is_directory


def test_files(host, get_vars):
    """ """
    distribution = host.system_info.distribution
    release = host.system_info.release

    print(f"distribution: {distribution}")
    print(f"release     : {release}")
    version = local_facts(host=host, fact="opengist").get("version")
    print(f"version     : {version}")

    install_dir = get_vars.get("opengist_install_path")
    defaults_dir = get_vars.get("opengist_defaults_directory")
    # config_dir = get_vars.get("opengist_config_dir")

    if "latest" in install_dir:
        install_dir = install_dir.replace("latest", version)

    files = []
    files.append("/usr/bin/opengist")

    if install_dir:
        files.append(f"{install_dir}/opengist")
    if defaults_dir and not distribution == "artix":
        files.append(f"{defaults_dir}/opengist")
    # if config_dir:
    #     files.append(f"{config_dir}/config.yml")

    for _file in files:
        f = host.file(_file)
        assert f.is_file


def test_user(host, get_vars):
    """ """
    user = get_vars.get("opengist_user", "{}").get("owner", "opengist")
    group = get_vars.get("opengist_user", "{}").get("group", "opengist")

    assert host.group(group).exists
    assert host.user(user).exists
    assert group in host.user(user).groups
    assert host.user(user).home == "/opt/opengist"


def test_service(host, get_vars):
    service = host.service("opengist")
    assert service.is_enabled
    assert service.is_running


def test_open_port(host, get_vars):
    for i in host.socket.get_listening_sockets():
        print(i)

    opengist_config = get_vars.get("opengist_config", {})
    listen_address = None

    # print(opengist_config)

    if isinstance(opengist_config, dict):
        opengist__http = opengist_config.get("http", {})
        listen_host = opengist__http.get("host")
        listen_port = opengist__http.get("port")

        if listen_host and listen_port:
            listen_address = f"{listen_host}:{listen_port}"

    if not listen_address:
        listen_address = "0.0.0.0:2222"

    print(listen_address)

    service = host.socket(f"tcp://{listen_address}")
    assert service.is_listening
