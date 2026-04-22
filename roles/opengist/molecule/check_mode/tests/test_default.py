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
    assert not d.is_directory
