import os
import pytest


@pytest.fixture(scope="module")
def salt_master_config(file_root, pillar_root):
    return {'this': {'is': {'my': ['config']}}}


def test_config_without_volume_mounting(master_container):
    output = master_container.run('cat /etc/salt/master.d/this.conf')
    assert output == 'is:\n  my:\n  - config\n'
    assert master_container['config']['volumes'] == [os.getcwd()]
