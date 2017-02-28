import os
import py
import yaml
import string
import logging
import tarfile
import factory
import factory.fuzzy
import requests_unixsocket
from functools import wraps
from docker import Client
from models import ContainerModel, MasterModel, MinionModel


logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


class BaseFactory(factory.Factory):

    class Meta:
        model = dict
        strategy = factory.BUILD_STRATEGY


class DockerClientFactory(factory.StubFactory):

    @classmethod
    def stub(cls, **kwargs):
        return Client(base_url='unix://var/run/docker.sock')


class NspawnClient(object):

    def __init__(self, base_url=None):
        self.session = requests_unixsocket.Session()
        self.base_url = base_url
        # self.session.get = self.wrapper(self.session.get)
        self.session.post = self.wrapper(self.session.post)
        self.session.delete = self.wrapper(self.session.delete)

    def wrapper(self, func):
        @wraps(func)
        def wrapper(path, *args, **kwargs):
            return func(self.base_url + path, *args, **kwargs)
        return wrapper

    def start(self, machine):
        return self.session.post('/start', data=dict(machine=machine))

    def create_container(self, **params):
        return self.session.post(
            '/clone', data=dict(machine=params['image'], target=params['name']))

    def config(self, config):
        for source_path in config['volumes']:
            bind = config['host_config']['binds'][source_path]
            data = dict(
                machine=config['name'],
                source_path=source_path,
                target_path=bind['bind'],
                mode=bind['mode'])
            self.session.post('/bind', data=data)

    def stop(self, machine):
        self.session.post('/stop', data=dict(machine=machine))

    def remove(self, machine):
        self.session.delete('/remove', data=dict(machine=machine))

    def drop(self, machine):
        self.session.post('/stop', data=dict(machine=machine))
        time.sleep(5)
        self.session.delete('/remove', data=dict(machine=machine))

    def copy_to(self, machine, source, target):
        return self.session.post(
            '/copy-to',
            data=dict(machine=machine, source=source, target=target)
        )

    def inspect_container(self, machine):
        return self.session.post('/inspect', data=dict(machine=machine))

    def create_host_config(self, **kwargs):
        return kwargs

    def put_archive(self, machine, target, data):
        pass


class NspawnClientFactory(factory.StubFactory):

    @classmethod
    def stub(cls, **kwargs):
        return NspawnClient(base_url='http+unix://%2Fvar%2Frun%2Fgunicorn.sock')


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
    client = factory.SubFactory(DockerClientFactory)

    @factory.lazy_attribute
    def volumes(self):
        volumes = [os.getcwd()]
        if os.getenv('SALT_REPO'):
            volumes.append(os.getenv('SALT_REPO'))
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
        salt_repo = os.getenv('SALT_REPO')
        if salt_repo and salt_repo in self.volumes:
            params['binds'][os.getenv('SALT_REPO')] = {
                'bind': '/salt/src/salt-devel/',
                'mode': 'rw'
            }

        return self.client.create_host_config(**params)


class ContainerFactory(BaseFactory):

    config = factory.SubFactory(ContainerConfigFactory)
    ip = None

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
        client.start(obj['config']['name'])

        data = client.inspect_container(obj['config']['name'])
        obj['ip'] = data['NetworkSettings']['IPAddress']

        try:
            resp = obj.run('salt --version')
            message = "{0}: {1}".format(
                obj['config']['salt_config']['conf_type'],
                resp.strip())
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
        conf_path = obj['container']['config']['salt_config']['conf_path']

        with tarfile.open(conf_path.strpath, mode='w') as archive:
            root = obj['container']['config']['salt_config']['root']
            for item in root.listdir():
                archive.add(
                    item.strpath,
                    arcname=item.strpath.replace(root.strpath, '.'))

        with conf_path.open('rb') as f:
            client.put_archive(
                obj['container']['config']['name'], '/etc/salt', f.read())

        res = client.exec_create(
            obj['container']['config']['name'], obj['cmd']
        )
        output = client.exec_start(res['Id'])
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


class MinionFactory(SaltFactory):
    id = factory.LazyAttribute(lambda o: o.container['config']['salt_config']['id'])
    cmd = 'salt-minion -d -l debug'

    class Meta:
        model = MinionModel
