import uuid
import time
import subprocess
import tarfile
import requests_unixsocket
from functools import wraps
from docker import Client


class DockerClient(Client):
    """ """

    def start(self, config):
        return super(DockerClient, self).start(config['name'])

    def drop(self, name):
        proc = subprocess.Popen(
            'docker rm -f {0} > /dev/null'.format(name), shell=True)
        out, err = proc.communicate()
        if proc.returncode:
            logger.error(err)
        else:
            logger.debug(out)

    def configure_salt(self, config):
        conf_path = config['salt_config']['conf_path']

        with tarfile.open(conf_path.strpath, mode='w') as archive:
            root = config['salt_config']['root']
            for item in root.listdir():
                archive.add(
                    item.strpath,
                    arcname=item.strpath.replace(root.strpath, '.'))

        with conf_path.open('rb') as f:
            self.put_archive(config['name'], '/etc/salt', f.read())


class NspawnClient(object):

    executables = dict()

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

    def start(self, config):
        self.session.post('/start', data=dict(machine=config['name']))
        self.config(config)

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

    def configure_salt(self, config):
        root = config['salt_config']['root']
        for item in root.listdir():
            client.copy_to(
                config['name'],
                item.strpath,
                item.strpath.replace(root.strpath, '/etc/salt'))

    def copy_to(self, machine, source, target):
        return self.session.post(
            '/copy-to',
            data=dict(machine=machine, source=source, target=target)
        )

    def inspect_container(self, machine):
        return self.session.post('/inspect', data=dict(machine=machine)).json()

    def create_host_config(self, **kwargs):
        return kwargs

    def exec_create(self, name, command):
        exec_id = uuid.uuid4()
        self.executables[exec_id] = dict(
            machine=self['config']['name'], command=command, stream=stream)
        return {'Id': exec_id}

    def exec_start(self, id, stream=None):
        resp = self['config']['client'].session.post(
            '/run', stream=stream, data=self.executables[id])
        if not stream:
            return resp.json()['stdoutdata']
        else:
            return resp.iter_lines()
