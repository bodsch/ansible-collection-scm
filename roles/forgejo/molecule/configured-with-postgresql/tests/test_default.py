# coding: utf-8
from __future__ import annotations, unicode_literals

import pytest
from helper.molecule import get_vars, infra_hosts, local_facts

testinfra_hosts = infra_hosts(host_name="instance")

# --- tests -----------------------------------------------------------------

# _facts = local_facts(host=host, fact="forgejo")


def test_user(host, get_vars):
    """ """
    user = get_vars.get("forgejo_system_user", "forgejo")
    group = get_vars.get("forgejo_system_group", "forgejo")
    home = get_vars.get("forgejo_working_dir", "/var/lib/forgejo")

    assert host.group(group).exists
    assert host.user(user).exists
    assert group in host.user(user).groups
    assert host.user(user).home == home


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
        _address = forgejo_server.get("http_addr")
        _port = forgejo_server.get("http_port")

        listen_address = f"{_address}:{_port}"
    else:
        listen_address = "127.0.0.1:3000"

    service = host.socket(f"tcp://{listen_address}")
    assert service.is_listening
