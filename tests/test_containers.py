# -*- coding: utf-8 -*-


def test_master_container_fixture(testdir):
    """Make sure that pytest accepts our fixture."""

    testdir.makepyfile("""
        def test_sth(master_container):
            assert master_container['config']['name'].startswith("master_")
    """)

    result = testdir.runpytest('-v')

    result.stdout.fnmatch_lines([
        '*::test_sth PASSED',
    ])

    assert result.ret == 0


def test_minion_container_fixture(testdir):
    """Make sure that pytest accepts our fixture."""

    testdir.makepyfile("""
        def test_sth(minion_container):
            assert minion_container['config']['name'].startswith("minion_")
    """)

    result = testdir.runpytest('-v')

    result.stdout.fnmatch_lines([
        '*::test_sth PASSED',
    ])

    assert result.ret == 0


def test_minion_fixture(testdir):
    """Make sure that pytest accepts our fixture."""

    testdir.makepyfile("""
        def test_sth(minion, minion_key_accepted):
            assert minion['container']['config']['name'].startswith("minion_")
    """)

    result = testdir.runpytest('-v')

    result.stdout.fnmatch_lines([
        '*::test_sth PASSED',
    ])

    assert result.ret == 0
