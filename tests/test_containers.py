# -*- coding: utf-8 -*-
import pytest


FIXTURES = [
    'docker_client',
    'salt_root',
    'pillar_root',
    'file_root',
    'salt_master_config',
    'salt_minion_config',
    'master_container_extras',
    'master_container',
    'minion_container_extras',
    'minion_container',
    'master',
    'minion',
    'minion_key_cached',
    'minion_key_accepted'
]


@pytest.mark.parametrize("fixture", FIXTURES)
def test_fixtures_accepted(testdir, fixture):
    """Make sure that pytest accepts our fixtures."""

    testdir.makepyfile("""
        def test_sth({fixture}):
            pass
    """.format(fixture=fixture))

    result = testdir.runpytest('-v')

    result.stdout.fnmatch_lines([
        '*::test_sth PASSED',
    ])

    assert result.ret == 0


def test_master_container(master_container):
    name = master_container['config']['name']
    assert name.startswith("master_")


def test_minion_container(minion_container):
    name = minion_container['config']['name']
    assert name.startswith("minion_")


def test_minion(minion, minion_key_accepted):
    name = minion['container']['config']['name']
    assert name.startswith("minion_")
