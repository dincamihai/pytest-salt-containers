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
from saltcontainers.factories import (
    BaseFactory,
    SaltConfigFactory,
    ContainerConfigFactory,
    NspawnClientFactory
)
from saltcontainers.models import (
    MasterModel as OrigMasterModel,
    MinionModel as OrigMinionModel
)

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


class MasterModel(OrigMasterModel):

    def salt_key_raw(self, *args):
        command = ['salt-key']
        command.extend(args)
        command.append('--output=json')
        return self['container'].run(' '.join(command))['stdoutdata']

    def salt(self, minion_id, salt_command, *args):
        command = "salt {0} {1} --output=json -l quiet".format(
            minion_id, salt_command, ' '.join(args))
        data = self['container'].run(command)['stdoutdata']
        try:
            return json.loads(data)
        except ValueError as err:
            raise ValueError(
                "{0}\nIncoming data: {1}".format(err.message, data))


class MinionModel(OrigMinionModel):

    def salt_call(self, salt_command, *args):
        command = "salt-call {0} {1} --output=json -l quiet".format(
            salt_command, ' '.join(args)
        )
        raw = self['container'].run(command)['stdoutdata']
        try:
            out = json.loads(raw)
        except ValueError:
            raise Exception(raw)
        return out['local']


class ContainerModel(dict):

    def run(self, command, stream=None):
        data = dict(
            machine=self['config']['name'], command=command, stream=stream)
        resp = self['config']['client'].session.post(
            '/run', stream=stream, data=data)
        if not stream:
            return resp.json()
        else:
            return resp.iter_lines()

    def remove(self):
        self['config']['client'].drop(self['config']['name'])


class ContainerFactory(BaseFactory):

    config = factory.SubFactory(ContainerConfigFactory, client=factory.SubFactory(NspawnClientFactory))
    ip = None

    class Meta:
        model = ContainerModel

    @classmethod
    def build(cls, **kwargs):
        obj = super(ContainerFactory, cls).build(**kwargs)
        assert obj['config']['image']
        client = obj['config']['client']

        client.create_container(**obj['config'])
        client.start(obj['config']['name'])
        client.config(obj['config'])
        data = client.inspect_container(obj['config']['name']).json()

        obj['ip'] = data['NetworkSettings']['IPAddress']

        try:
            resp = obj.run('salt --version')
            message = "{0}: {1}".format(
                obj['config']['salt_config']['conf_type'],
                resp['stdoutdata'].strip())
            logger.info(message)
        except TypeError:
            pass

        return obj


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
