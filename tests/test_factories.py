import os
import pytest
from saltcontainers.factories import ContainerConfigFactory


@pytest.fixture(scope="module")
def salt_master_config(file_root, pillar_root):
    return {'this': {'is': {'my': ['config']}}}


def test_config_without_volume_mounting(master):
    output = master['container'].run('cat /etc/salt/master.d/this.conf')
    assert output == 'is:\n  my:\n  - config\n'
    assert master['container']['config']['volumes'] == [os.getcwd()]


def test_container_config_image():
    config = ContainerConfigFactory(salt_config=None, host_config=None)
    assert config['image'] == 'registry.mgr.suse.de/toaster-sles12sp1-products'


def test_container_config__host_config(docker_client):
    config = ContainerConfigFactory(
        salt_config=None, docker_client=docker_client)
    assert config['host_config']
