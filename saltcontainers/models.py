import re
import json
import yaml
import tarfile
import logging
import six
import subprocess
from .utils import retry, load_json

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


class ContainerModel(dict):

    def _get_container_pid(self, pid):
        container_pid = None
        if pid:
            with open('/proc/{0}/status'.format(pid), 'rb') as _file:
                contents = _file.read()
                try:
                    container_pid = re.search("NSpid.+{0}.+".format(pid), contents).group().split('\t')[-1]
                except:
                    logger.warning("Unable to obtain container pid from {0}".format(pid))
        return container_pid

    def kill(self, cmd_exec_id):
        pid = self['config']['client'].exec_inspect(cmd_exec_id).get('Pid', None)
        container_pid = self._get_container_pid(pid)
        self.run('kill -9 {0}'.format(container_pid))

    @retry()
    def run(self, command, stream=False):
        return self['config']['client'].run(
            self['config']['name'], command, stream=stream)

    @retry()
    def check_run(self, command, stream=False):
        cmd_exec = self['config']['client'].exec_create(self['config']['name'], cmd=command, stderr=False)
        return cmd_exec['Id'], self['config']['client'].exec_start(cmd_exec['Id'], stream=stream)

    def get_suse_release(self):
        info = dict()
        content = self.run('cat /etc/SuSE-release')
        for line in content.split('\n'):
            match = re.match('([a-zA-Z]+)\s*=\s*(\d+)', line)
            if match:
                info.update([[match.group(1), int(match.group(2))]])
        return info

    def get_os_release(self):
        content = self.run('cat /etc/os-release')
        return dict(
            filter(
                lambda it: len(it) == 2,
                [it.replace('"', '').strip().split('=') for it in content.split('\n')]
            )
        )

    def connect(self):
        for item in self['config']['networking_config']['EndpointsConfig'].keys():
            self['config']['client'].connect_container_to_network(self['config']['name'], item)

    def disconnect(self):
        for item in self['config']['networking_config']['EndpointsConfig'].keys():
            self['config']['client'].disconnect_container_from_network(self['config']['name'], item)

    def remove(self):
        self['config']['client'].stop(self['config']['name'])
        self['config']['client'].remove_container(
            self['config']['name'], v=True)


class BaseModel(dict):

    def salt_call(self, salt_command, *args):
        command = "salt-call {0} {1} --output=json -l quiet".format(
            salt_command, ' '.join(args)
        )
        raw = self['container'].run(command)
        try:
            out = json.loads(raw or '{}')
        except ValueError:
            raise Exception(raw)
        return out.get('local')

    def start(self):
        self['container'].run(self['cmd'])


class MasterModel(BaseModel):

    def salt_key_raw(self, *args):
        command = ['salt-key']
        command.extend(args)
        command.append('--output=json')
        return self['container'].run(' '.join(command))

    def salt_key(self, *args):
        return json.loads(self.salt_key_raw(*args))

    def salt_key_accept(self, minion_id):
        return self.salt_key_raw('-a', minion_id, '-y')

    def salt(self, minion_id, salt_command, *args):
        command = "salt {0} {1} --output=json -l quiet".format(
            minion_id, salt_command, ' '.join(args))
        data = self['container'].run(command)
        return load_json(data)

    def salt_run(self, command, *args):
        docker_command = "salt-run {0} {1} --output=json -l quiet".format(
            command, ' '.join(args))
        data = self['container'].run(docker_command)
        return load_json(data)

    def salt_ssh(self, target, cmd):
        roster = self['container']['config']['salt_config']['roster']
        target_id = target['config']['name']
        SSH = "salt-ssh -l quiet -i --out json --key-deploy --passwd {0} {1} {{0}}".format(
            target['ssh_config']['password'], target_id)
        data = self['container'].run(SSH.format(cmd))
        return load_json(data)[target_id]

    def update_roster(self):
        roster = self['container']['config']['salt_config']['root'] / 'roster'
        content = {}
        for item in self['container']['config']['salt_config']['roster']:
            content[item['config']['name']] = {
                "host": item["ip"],
                "user": item['ssh_config']['user'],
                "password": item['ssh_config']['password']
            }
        roster.write(yaml.safe_dump(content, default_flow_style=False))

        self['container']['config']['client'].copy_to(self, roster.strpath, '/etc/salt/')


class MinionModel(BaseModel):

    def stop(self):
        self['container'].run('pkill salt-minion')
