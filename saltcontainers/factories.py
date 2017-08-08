import os
import py
import yaml
import string
import logging
import factory
import factory.fuzzy
from models import ContainerModel, MasterModel, MinionModel
from clients import DockerClient, NspawnClient


logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


class BaseFactory(factory.Factory):

    class Meta:
        model = dict
        strategy = factory.BUILD_STRATEGY


class SaltConfigFactory(BaseFactory):

    tmpdir = None
    root = factory.LazyAttribute(
        lambda o: o.tmpdir.ensure_dir(o.factory_parent.name))
    conf_path = factory.LazyAttribute(lambda o: o.tmpdir / '{0}.conf.tar'.format(o.factory_parent.name))
    conf_type = None
    config = {}
    pillar = {}
    sls = {}
    id = factory.fuzzy.FuzzyText(
        length=5, prefix='id_', chars=string.ascii_letters)

    @factory.post_generation
    def extra_configs(obj, create, extracted, **kwargs):
        if extracted:
            config_path = obj['root'] / '{}.d'.format(obj['conf_type'])
            config_path.ensure_dir()
            for name, config in extracted.items():
                config_file = config_path / '{0}.conf'.format(name)
                config_file.write(
                    yaml.safe_dump(config, default_flow_style=False))

    @factory.post_generation
    def post(obj, create, extracted, **kwargs):
        config_path = obj['root'] / '{}.d'.format(obj['conf_type'])
        config_path.ensure_dir()
        config_file = obj['root'] / obj['conf_type']
        main_config = {
            'include': '{0}.d/*'.format(obj['conf_type'])
        }
        if obj['conf_type'] in ['minion', 'proxy']:
            main_config['id'] = obj['id']

        config_file.write(
            yaml.safe_dump(main_config, default_flow_style=False))

        config_path = obj['root'] / '{}.d'.format(obj['conf_type'])
        for name, config in obj['config'].items():
            config_file = config_path / '{0}.conf'.format(name)
            config_file.write(yaml.safe_dump(config, default_flow_style=False))

        pillar_path = obj['root'].ensure_dir('pillar')
        for name, content in obj['pillar'].items():
            sls_file = pillar_path / '{0}.sls'.format(name)
            sls_file.write(yaml.safe_dump(content, default_flow_style=False))

        sls_path = obj['root'].ensure_dir('sls')
        for name, source in obj['sls'].items():
            sls_file = sls_path / '{0}.sls'.format(name)
            sls_file.write(py.path.local(source).read())


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


class SyndicSaltConfigFactory(MasterSaltConfigFactory):

    @factory.post_generation
    def syndic_id(obj, create, extracted, **kwargs):
        config_path = obj['root'] / 'minion.d'
        config_path.ensure_dir()
        config_file = obj['root'] / 'minion'
        main_config = {'include': 'minion.d/*'}
        main_config['id'] = obj['id']
        config_file.write(
            yaml.safe_dump(main_config, default_flow_style=False))


class ContainerConfigFactory(BaseFactory):
    name = factory.fuzzy.FuzzyText(
        length=5, prefix='container_', chars=string.ascii_letters)
    salt_config = factory.SubFactory(SaltConfigFactory)
    image = None
    entrypoint = '/bin/bash'
    environment = dict()
    tty = True
    stdin_open = True
    working_dir = "/salt-toaster/"
    ports = [4000, 4506]

    @factory.lazy_attribute
    def client(self):
        if self.factory_parent.type == 'docker':
            return DockerClient(base_url='unix://var/run/docker.sock')
        elif self.factory_parent.type == 'nspawn':
            return NspawnClient('http+unix:///var/run/gunicorn.sock')

    @factory.lazy_attribute
    def volumes(self):
        volumes = [os.getcwd()]
        if os.environ.get('FLAVOR') == 'devel' and os.environ.get('SALT_REPO'):
            volumes.append(os.environ['SALT_REPO'])
        return volumes

    @factory.lazy_attribute
    def host_config(self):
        params = dict(
            port_bindings={},
            binds={
                os.getcwd(): {
                    'bind': "/salt-toaster/",
                    'mode': 'ro'
                }
            }
        )
        if os.environ.get('SALT_REPO') in self.volumes:
            params['binds'][os.environ['SALT_REPO']] = {
                'bind': '/salt/src/salt-devel',
                'mode': 'rw'
            }
        return self.client.create_host_config(**params)

    @factory.post_generation
    def networking_config(self, create, extracted, **kwargs):
        if not self['client'].networks(names=[extracted['name']]):
            self['client'].create_network(**extracted)

        self['networking_config'] = self['client'].create_networking_config({
            extracted['name']: self['client'].create_endpoint_config()
        })


class ContainerFactory(BaseFactory):

    ip = None
    type = 'docker'
    config = factory.SubFactory(
        ContainerConfigFactory,
        networking_config=dict(name="network1", driver="bridge")
    )

    class Meta:
        model = ContainerModel

    @classmethod
    def build(cls, **kwargs):
        obj = super(ContainerFactory, cls).build(**kwargs)
        assert obj['config']['image']
        client = obj['config']['client']
        client.create_container(
            **{
                k: obj['config'][k] for k in obj['config'].keys()
                if k not in ['salt_config', 'client']
            }
        )
        obj['config']['client'].start(obj['config'])
        obj['ip'] = obj['config']['client'].getip(obj['config']['name'])

        try:
            resp = obj.run('salt --version')
            message = "{0}: {1}".format(
                obj['config']['salt_config']['conf_type'], resp.strip())
            logger.info(message)
        except TypeError:
            pass

        return obj

    @factory.post_generation
    def ip(self, create, extracted, **kwargs):
        if not create:
            return extracted


class SaltFactory(BaseFactory):

    container = factory.SubFactory(ContainerFactory)

    @classmethod
    def build(cls, **kwargs):
        obj = super(SaltFactory, cls).build(**kwargs)
        client = obj['container']['config']['client']

        client.configure_salt(obj['container']['config'])

        output = client.run(
            obj['container']['config']['name'], obj['cmd']
        )
        assert 'executable file not found' not in output
        return obj


class MasterFactory(SaltFactory):
    id = factory.LazyAttribute(lambda o: o.container['config']['salt_config']['id'])
    cmd = 'salt-master -d -l debug'
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


class SyndicFactory(MasterFactory):

    container = factory.SubFactory(
        ContainerFactory,
        config__salt_config=factory.SubFactory(SyndicSaltConfigFactory)
    )

    @classmethod
    def build(cls, **kwargs):
        obj = super(SyndicFactory, cls).build(**kwargs)
        cmd = 'salt-syndic -d -l debug'
        client = obj['container']['config']['client']
        output = client.run(obj['container']['config']['name'], cmd)
        assert 'executable file not found' not in output
        return obj


class MinionFactory(SaltFactory):
    id = factory.LazyAttribute(lambda o: o.container['config']['salt_config']['id'])
    cmd = 'salt-minion -d -l debug'

    class Meta:
        model = MinionModel
