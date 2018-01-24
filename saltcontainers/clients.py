import time
import urllib
import subprocess
import tarfile
import logging
import requests_unixsocket
from functools import wraps
from docker import Client


logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


class DockerClient(Client):
    """ """

    def start(self, config):
        return super(DockerClient, self).start(config['name'])

    def run(self, name, command, stream=None):
        cmd_exec = self.exec_create(name, cmd=command)
        return self.exec_start(cmd_exec['Id'], stream=stream)

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

    def getip(self, machine):
        return self.inspect_container(machine)['NetworkSettings']['Networks'].popitem()[1]['IPAddress']


class NspawnClient(object):

    def __init__(self, base_url):
        self.session = requests_unixsocket.Session()
        if base_url.startswith("http+unix"):
            self.base_url = "http+unix://{0}".format(
                urllib.quote_plus(base_url.replace('http+unix://', '')))
        else:
            self.base_url = base_url
        # self.session.get = self.wrapper(self.session.get)
        self.session.post = self.wrapper(self.session.post)
        self.session.delete = self.wrapper(self.session.delete)

    def wrapper(self, func):
        @wraps(func)
        def wrapper(path, *args, **kwargs):
            resp = func(self.base_url + path, *args, **kwargs)
            resp.raise_for_status()
            return resp
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
            config['client'].copy_to(
                config['name'],
                item.strpath,
                item.strpath.replace(root.strpath, '/etc/salt'))

    def copy_to(self, machine, source, target):
        return self.session.post(
            '/copy-to',
            data=dict(machine=machine, source=source, target=target))

    def getip(self, machine):
        data = self.session.post(
            '/inspect', data=dict(machine=machine, interface='host0')).json()
        return data['NetworkSettings']['IPAddress']

    def create_host_config(self, **kwargs):
        return kwargs

    def run(self, name, command, stream=False):
        resp = self.session.post(
            '/run',
            stream=stream,
            data=dict(machine=name, command=command, stream=stream))
        if not stream:
            return resp.json()['stdoutdata']
        else:
            return resp.iter_lines()
