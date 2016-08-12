import re
import json
import subprocess
from utils import retry


class ContainerModel(dict):

    @retry()
    def run(self, command, stream=False):
        cmd_exec = self['config']['docker_client'].exec_create(
            self['config']['name'], cmd=command)
        output = self['config']['docker_client'].exec_start(cmd_exec['Id'], stream=stream)
        return output

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

    def remove(self):
        name = self['config']['name']
        proc = subprocess.Popen('docker rm -f {0}'.format(name), shell=True)
        out, err = proc.communicate()
        if proc.returncode:
            print err
        else:
            print out


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
        docker_command = "salt {0} {1} --output=json -l quiet".format(
            minion_id, salt_command, ' '.join(args))
        data = self['container'].run(docker_command)
        try:
            return json.loads(data)
        except ValueError as err:
            raise ValueError(
                "{0}\nIncoming data: {1}".format(err.message, data))


class MinionModel(dict):

    def salt_call(self, salt_command, *args):
        docker_command = "salt-call {0} {1} --output=json -l quiet".format(
            salt_command, ' '.join(args)
        )
        raw = self['container'].run(docker_command)
        try:
            out = json.loads(raw)
        except ValueError:
            raise Exception(raw)
        return out['local']
