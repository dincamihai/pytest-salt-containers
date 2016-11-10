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


@pytest.fixture(scope="module")
def salt_master_config(file_root, pillar_root):
    return {'this': {'is': {'my': ['config']}}}


def test_configuration(testdir):
    testdir.makepyfile("""
        def test_sth(request):
            assert request.config.getini('IMAGE') == 'registry.mgr.suse.de/toaster-sles12sp1-products'
            assert request.config.getini('MINION_IMAGE') == 'registry.mgr.suse.de/toaster-sles12sp1-products'
            assert request.config.getini('TAGS') == ['#sometag', '#some-other-tag']
    """)

    result = testdir.runpytest('-v')

    result.stdout.fnmatch_lines(['*::test_sth PASSED'])


def test_config_without_volume_mounting(testdir):
    testdir.makepyfile("""
        import os


        def test_sth(master):
            output = master['container'].run('cat /etc/salt/master.d/this.conf')
            assert master['container']['config']['volumes'] == [os.getcwd()]
    """)

    result = testdir.runpytest('-v')

    result.stdout.fnmatch_lines(['*::test_sth PASSED'])


def test_container_config_image(testdir):
    testdir.makepyfile("""
        from saltcontainers.factories import ContainerConfigFactory


        def test_sth():
            config = ContainerConfigFactory(salt_config=None, host_config=None)
            assert config['image'] is None
    """)

    result = testdir.runpytest('-v')

    result.stdout.fnmatch_lines(['*::test_sth PASSED'])


def test_container_config__host_config(testdir):
    testdir.makepyfile("""
        from mock import MagicMock
        from saltcontainers.factories import ContainerConfigFactory


        def test_sth():
            config = ContainerConfigFactory(
                salt_config=None, docker_client=MagicMock())
            assert config['host_config']
    """)

    result = testdir.runpytest('-v')

    result.stdout.fnmatch_lines(['*::test_sth PASSED'])


def test_container_config__salt_config__sls(testdir):
    (testdir.tmpdir / 'top.sls').write( """
        base:
          some-minion-id:
            - latest
    """)
    (testdir.tmpdir / 'latest.sls').write("""
        abc:
          pkg.latest:
            - name: some-package
    """)
    testdir.makepyfile("""
        import yaml
        from mock import MagicMock
        from saltcontainers.factories import ContainerConfigFactory


        def test_sth(docker_client, salt_root, file_root):
            config = ContainerConfigFactory(
                name='container-test',
                docker_client=docker_client,
                salt_config__tmpdir=salt_root,
                salt_config__sls={
                    'top': 'top.sls',
                    'latest': 'latest.sls'
                }
            )
            file_root_dir = 'sls'
            assert file_root == "/etc/salt/" + file_root_dir
            top_sls = yaml.load(
                (salt_root / 'container-test' / file_root_dir / 'top.sls').read()
            )
            assert top_sls['base']['some-minion-id'] == ['latest']
            latest_sls = yaml.load(
                (salt_root / 'container-test' / file_root_dir / 'latest.sls').read()
            )
            assert latest_sls['abc']['pkg.latest'][0]['name'] == 'some-package'
    """)

    result = testdir.runpytest('-v')

    result.stdout.fnmatch_lines(['*::test_sth PASSED'])
