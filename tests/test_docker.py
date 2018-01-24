import pytest


pytestmark = pytest.mark.usefixtures('config')


@pytest.fixture
def config(testdir):
    testdir.makeini("""
        [pytest]
        IMAGE = registry.mgr.suse.de/toaster-sles12sp1-products
        MINION_IMAGE = registry.mgr.suse.de/toaster-sles12sp1-products
        TAGS = #sometag #some-other-tag
    """)


def test_docker_minion_ping(testdir):
    testdir.makepyfile("""
        def test_sth(master, minion, minion_key_accepted):
            assert master.salt(minion['id'], "test.ping")[minion['id']] is True
    """)

    result = testdir.runpytest('-v')

    result.stdout.fnmatch_lines(['*::test_sth PASSED'])
