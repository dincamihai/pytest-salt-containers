import pytest
from mock import patch, Mock, MagicMock


pytest_plugins = 'pytester'


@pytest.fixture
def mocks(request, testdir):
    mock_docker_client = MagicMock(
        **{
            'return_value.inspect_container.return_value': {
                'NetworkSettings': {'IPAddress': 'fake-ip'}},
            'return_value.exec_start.return_value': '{"minions_pre": ["abc"]}'
        }
    )
    testdir.makeini("""
        [pytest]
        IMAGE = myregistry/defaultimage
        MINION_IMAGE = myregistry/minion_image
    """)
    my_mocks = patch.multiple(
        'saltcontainers.plugin',
        Client=mock_docker_client,
        retry=Mock(return_value=Mock(return_value=Mock(return_value=True)))
    )
    my_mocks.start()
    request.addfinalizer(my_mocks.stop)
