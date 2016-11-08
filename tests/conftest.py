import pytest
from mock import patch, MagicMock


pytest_plugins = 'pytester'


@pytest.fixture
def mocks(request, testdir):
    testdir.makeini("""
        [pytest]
        IMAGE = myregistry/defaultimage
        MINION_IMAGE = myregistry/minion_image
    """)
    plugin_mocks = patch.multiple(
        'saltcontainers.plugin',
        Client=MagicMock(**{
            'return_value.inspect_container.return_value': {
                'NetworkSettings': {'IPAddress': 'fake-ip'}}
        }))
    salt_key_mock = patch(
        'saltcontainers.factories.MasterModel.salt_key',
        **{'return_value.__getitem__.return_value.__contains__.return_value': True})
    plugin_mocks.start()
    request.addfinalizer(plugin_mocks.stop)
    salt_key_mock.start()
    request.addfinalizer(salt_key_mock.stop)
