import os
import py
import yaml
import json
import time
import string
import logging
import tarfile
import factory
from faker import Faker
from functools import wraps
import requests_unixsocket
from utils import retry
from saltcontainers.factories import (
    BaseFactory,
    SaltConfigFactory,
    ContainerConfigFactory,
    NspawnClientFactory,
    ContainerFactory as OrigContainerFactory
)
from saltcontainers.models import (
    ContainerModel as OrigContainerModel,
    MasterModel,
    MinionModel
)

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


class ContainerModel(OrigContainerModel):

    @retry()
    def run(self, command, stream=None):
        data = dict(
            machine=self['config']['name'], command=command, stream=stream)
        resp = self['config']['client'].session.post(
            '/run', stream=stream, data=data)
        if not stream:
            return resp.json()['stdoutdata']
        else:
            return resp.iter_lines()

    def remove(self):
        self['config']['client'].drop(self['config']['name'])


class ContainerFactory(OrigContainerFactory):

    config = factory.SubFactory(ContainerConfigFactory, client=factory.SubFactory(NspawnClientFactory))

    class Meta:
        model = ContainerModel

    @staticmethod
    def start(config):
        config['client'].start(config['name'])
        config['client'].config(config)


class SaltFactory(BaseFactory):

    container = factory.SubFactory(ContainerFactory)

    @classmethod
    def build(cls, **kwargs):
        obj = super(SaltFactory, cls).build(**kwargs)
        client = obj['container']['config']['client']

        root = obj['container']['config']['salt_config']['root']
        for item in root.listdir():
            client.copy_to(
                obj['container']['config']['name'],
                item.strpath,
                item.strpath.replace(root.strpath, '/etc/salt')
            )

        output = obj['container'].run(obj['cmd'])
        assert 'executable file not found' not in output
        return obj


class MasterSaltConfigFactory(SaltConfigFactory):

    @factory.post_generation
    def apply_states(obj, create, extracted, **kwargs):
        if extracted:
            destination = 'masterless'
            config_path = obj['root'] / 'minion.d'
            config_path.ensure_dir()
            (config_path / 'masterless.conf').write(
                yaml.safe_dump(
                    {
                        'file_client': 'local',
                        'file_roots': {
                            'base': ["/etc/salt/{}".format(destination)]
                        },
                        'pillar_roots': {'base': ["/etc/salt/pillar"]}
                    },
                    default_flow_style=False
                )
            )
            sls_path = obj['root'].ensure_dir(destination)
            for name, source in extracted.items():
                sls_file = sls_path / '{0}.sls'.format(name)
                sls_file.write(py.path.local(source).read())

    @factory.post_generation
    def roster(obj, create, extracted, **kwargs):
        if extracted:
            roster = obj['root'] / 'roster'
            roster.write(yaml.safe_dump(extracted, default_flow_style=False))


class MasterFactory(SaltFactory):
    id = factory.LazyAttribute(
        lambda o: o.container['config']['salt_config']['id'])
    cmd = 'salt-master -d'
    container = factory.SubFactory(
        ContainerFactory,
        config__salt_config=factory.SubFactory(MasterSaltConfigFactory)
    )

    class Meta:
        model = MasterModel

    @classmethod
    def build(cls, **kwargs):
        obj = super(MasterFactory, cls).build(**kwargs)
        obj['container'].run("salt-call --local state.apply")
        return obj


class MinionFactory(SaltFactory):
    id = factory.LazyAttribute(
        lambda o: o.container['config']['salt_config']['id'])
    cmd = 'salt-minion -d'

    class Meta:
        model = MinionModel
