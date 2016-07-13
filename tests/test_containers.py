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


pytestmark = pytest.mark.usefixtures('mocks')


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


def test_master_container(testdir):

    testdir.makepyfile("""
        def test_sth(master_container):
            name = master_container['config']['name']
            assert name.startswith("master_")
    """)

    result = testdir.runpytest('-v')

    result.stdout.fnmatch_lines(['*::test_sth PASSED'])


def test_minion_container(testdir):
    testdir.makepyfile("""
        def test_sth(minion_container):
            name = minion_container['config']['name']
            assert name.startswith("minion_")
    """)

    result = testdir.runpytest('-v')

    result.stdout.fnmatch_lines(['*::test_sth PASSED'])


def test_minion_container_config_image(testdir):
    testdir.makepyfile("""
        def test_sth(minion_container):
            assert minion_container['config']['image'] == 'myregistry/minion_image'
    """)

    result = testdir.runpytest('-v')

    result.stdout.fnmatch_lines(['*::test_sth PASSED'])


def test_minion(testdir):
    testdir.makepyfile("""
        def test_sth(minion, minion_key_accepted):
            name = minion['container']['config']['name']
            assert name.startswith("minion_")
    """)

    result = testdir.runpytest('-v')

    result.stdout.fnmatch_lines(['*::test_sth PASSED'])
