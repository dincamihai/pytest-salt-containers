# -*- coding: utf-8 -*-

import pytest
from docker import Client
from faker import Faker
from utils import retry
from saltcontainers.factories import (
    ContainerFactory, MasterFactory, SyndicFactory, MinionFactory
)


def pytest_addoption(parser):
    parser.addini('IMAGE', help='docker image')
    parser.addini(
        'BASE_IMAGE', help='minimal docker image used to start bare containers')
    parser.addini('MINION_IMAGE', help='minion docker image')
    parser.addini(
        'TAGS',
        help='assign tags for this configuration',
        type='args'
    )


@pytest.fixture(scope="session")
def docker_client():
    client = Client(base_url='unix://var/run/docker.sock')
    return client


@pytest.fixture(scope="session")
def salt_root(tmpdir_factory):
    return tmpdir_factory.mktemp("salt")


@pytest.fixture(scope="session")
def pillar_root(salt_root):
    salt_root.mkdir('pillar')
    return '/etc/salt/pillar'


@pytest.fixture(scope="session")
def file_root(salt_root):
    salt_root.mkdir('sls')
    return '/etc/salt/sls'


@pytest.fixture(scope="module")
def salt_master_config(file_root, pillar_root):
    return {
        'base_config': {
            'hash_type': 'sha384',
            'pillar_roots': {
                'base': [pillar_root]
            },
            'file_roots': {
                'base': [file_root]
            }
        }
    }


@pytest.fixture(scope="module")
def salt_minion_config(master_container, salt_root):
    return {
        'master': master_container['ip'],
        'hash_type': 'sha384',
    }


@pytest.fixture(scope="module")
def master_container_extras():
    return dict()


@pytest.fixture(scope="module")
def master_container(request, salt_root, master_container_extras, salt_master_config):
    fake = Faker()
    obj = ContainerFactory(
        config__name='master_{0}_{1}'.format(fake.word(), fake.word()),
        config__image=request.config.getini('IMAGE'),
        config__salt_config__tmpdir=salt_root,
        config__salt_config__conf_type='master',
        config__salt_config__config=salt_master_config,
        config__salt_config__post__id='{0}_{1}'.format(fake.word(), fake.word()),
        **master_container_extras
    )
    request.addfinalizer(obj.remove)
    return obj


@pytest.fixture(scope="module")
def minion_container_extras():
    return dict()


@pytest.fixture(scope="module")
def minion_container(request, salt_root, minion_container_extras, salt_minion_config):
    fake = Faker()
    image = request.config.getini('MINION_IMAGE') or request.config.getini('IMAGE')
    obj = ContainerFactory(
        config__name='minion_{0}_{1}'.format(fake.word(), fake.word()),
        config__image=image,
        config__salt_config__tmpdir=salt_root,
        config__salt_config__conf_type='minion',
        config__salt_config__config={
            'base_config': salt_minion_config
        },
        **minion_container_extras
    )
    request.addfinalizer(obj.remove)
    return obj


@pytest.fixture(scope="module")
def master(request, master_container):
    return MasterFactory(container=master_container)


@pytest.fixture(scope="module")
def minion(request, minion_container):
    out = MinionFactory(container=minion_container)
    return out


def wait_cached(master, minion):
    command = 'salt-run --out json -l quiet state.event tagmatch="salt/auth"'
    for item in master['container'].run(command, stream=True):
        if minion['id'] in item:
            break
    assert minion['id'] in master.salt_key(minion['id'])['minions_pre']


def accept(master, minion):
    master.salt_key_accept(minion['id'])
    tag = "salt/minion/{0}/start".format(minion['id'])
    master['container'].run(
        'salt-run state.event tagmatch="{0}" count=1'.format(tag))
    assert minion['id'] in master.salt_key(minion['id'])['minions']


@pytest.fixture(scope='module')
def minion_key_cached(master, minion):
    wait_cached(master, minion)


@pytest.fixture(scope='module')
def minion_key_accepted(master, minion, minion_key_cached):
    accept(master, minion)


def default_master_args(request, salt_root, file_root, pillar_root, is_syndic=False, master=None):
    fake = Faker()

    base_config = {
        'pillar_roots': {'base': [pillar_root]},
        'file_roots': {'base': [file_root]}
    }
    if is_syndic and master:
        base_config['syndic_master'] = master['container']['ip']

    args = dict(
        container__config__name='{0}_{1}_{2}'.format(
            'syndic' if is_syndic else 'master', fake.word(), fake.word()),
        container__config__image=request.config.getini('IMAGE'),
        container__config__salt_config__conf_type='master',
        container__config__salt_config__tmpdir=salt_root,
        container__config__salt_config__config={'base_config': base_config}
    )

    return args


def default_minion_args(request, salt_root, master_ip):
    fake = Faker()
    return dict(
        container__config__name='minion_{0}_{1}'.format(
            fake.word(), fake.word()),
        container__config__image=(
            request.config.getini('IMAGE') or
            request.config.getini('MINION_IMAGE')),
        container__config__salt_config__conf_type='minion',
        container__config__salt_config__tmpdir=salt_root,
        container__config__salt_config__config={
            'base_config': {'master': master_ip}
        }
    )


def setup_minion(request, salt_root, master, minion_item):
    sub_config_item = dict(id=None, fixture=None)

    minion_args = default_minion_args(
        request, salt_root, master['container']['ip'])
    minion_args.update(minion_item.get('config', {}))

    minion = MinionFactory(**minion_args)
    request.addfinalizer(minion['container'].remove)

    sub_config_item['id'] = minion['id']
    sub_config_item['fixture'] = minion

    wait_cached(master, minion)
    accept(master, minion)

    return sub_config_item


def setup_master(request, salt_root, file_root, pillar_root, item, is_syndic=False, master=None):
    config_item = dict(id=None, fixture=None, syndics=[], minions=[])

    master_args = default_master_args(
        request,
        salt_root,
        file_root,
        pillar_root,
        is_syndic,
        master)

    master_args.update(item.get('config', {}))
    Factory = MasterFactory if not is_syndic else SyndicFactory
    obj = Factory(**master_args)
    request.addfinalizer(obj['container'].remove)

    config_item['id'] = obj['id']
    config_item['fixture'] = obj

    for syndic_item in item.get('syndics', []):
        sub_config_item = setup_master(
            request,
            salt_root,
            file_root,
            pillar_root,
            syndic_item,
            is_syndic=True,
            master=obj)
        config_item['syndics'].append(sub_config_item)
        syndic_item.update(sub_config_item)

    for minion_item in item.get('minions', []):
        sub_config_item = setup_minion(
            request,
            salt_root,
            obj,
            minion_item)
        config_item['minions'].append(sub_config_item)
        minion_item.update(sub_config_item)

    if is_syndic:
        wait_cached(master, obj)
        accept(master, obj)

    return config_item


@pytest.fixture(scope='module')
def setup(request, module_config, salt_root, pillar_root, file_root):
    config = dict(masters=[])
    for item in module_config['masters']:
        config_item = setup_master(
            request, salt_root, file_root, pillar_root, item
        )
        config['masters'].append(config_item)
        item.update(config_item)

    for item in module_config.get('containers', []):
        config_item = dict(id=None, fixture=None)
        container = ContainerFactory(
            config__image=request.config.getini('BASE_IMAGE'),
            config__salt_config__tmpdir=salt_root,
            config__salt_config=None,
            config__volumes=None,
            config__host_config=None)
        config_item['id'] = container['config']['name']
        config_item['fixture'] = container
        request.addfinalizer(container.remove)
        config['containers'].append(config_item)

    return config, module_config
