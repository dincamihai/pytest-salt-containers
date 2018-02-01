import re
import json
import yaml
import tarfile
import logging
import subprocess
from utils import retry

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


class ContainerModel(dict):

    @retry()
    def run(self, command, stream=False):
        return self['config']['client'].run(
            self['config']['name'], command, stream=stream)

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


class MasterModel(dict):

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
        try:
            return json.loads(data)
        except ValueError as err:
            raise ValueError(
                "{0}\nIncoming data: {1}".format(err.message, data))
        except TypeError as err:
            raise TypeError(
                "{0}\nIncoming data: {1}".format(err.message, data))

    def salt_run(self, command, *args):
        docker_command = "salt-run {0} {1} --output=json -l quiet".format(
            command, ' '.join(args))
        data = self['container'].run(docker_command)
        try:
            return json.loads(data)
        except ValueError as err:
            raise ValueError(
                "{0}\nIncoming data: {1}".format(err.message, data))

    def salt_ssh(self, target, cmd):
        roster = self['container']['config']['salt_config']['roster']
        target_id = target['config']['name']
        SSH = "salt-ssh -l quiet -i --out json --key-deploy --passwd {0} {1} {{0}}".format(
            target['ssh_config']['password'], target_id)
        data = self['container'].run(SSH.format(cmd))
        try:
            json_data = json.loads(str(data))
        except ValueError as err:
            raise ValueError(
                "{0}\nIncoming data: {1}".format(err.message, data))
        except TypeError as err:
            raise TypeError(
                "{0}\nIncoming data: {1}".format(err.message, data))
        return json_data[target_id]

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


class MinionModel(dict):

    def salt_call(self, salt_command, *args):
        command = "salt-call {0} {1} --output=json -l quiet".format(
            salt_command, ' '.join(args)
        )
        raw = self['container'].run(command)
        try:
            out = json.loads(raw)
        except ValueError:
            raise Exception(raw)
        return out['local']

    def stop(self):
        self['container'].run('pkill salt-minion')

    def start(self):
        self['container'].run(self['cmd'])
