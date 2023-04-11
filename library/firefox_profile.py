#!/usr/bin/python

from ansible.module_utils.basic import *
from collections import OrderedDict
import os.path
import subprocess
import configparser
import shutil


class FirefoxProfiles:
    """Class to manage firefox profiles."""

    def __init__(self, path):
        self.path = os.path.expanduser(path)
        self.profiles_ini = os.path.join(self.path, 'profiles.ini')
        self.config = configparser.RawConfigParser()
        # Make options case sensitive
        self.config.optionxform = str
        self.read()

    def read(self):
        self.config.read(self.profiles_ini)

    def write(self):
        with open(self.profiles_ini, 'w') as f:
            self.config.write(f, spaces_around_delimiters=False)

        # Update state with the new file.
        self.read()

    def get(self, name, get_section_name=False):
        for section in self.config.sections():
            if section.startswith('Profile'):
                if self.config[section]['Name'] == name:
                    if get_section_name:
                        return dict(self.config[section]), section
                    else:
                        return dict(self.config[section])

    def get_default(self, **kwargs):
        for section in self.config.sections():
            if section.startswith('Install'):
                default_path = self.config[section]['Default']
                for s2 in self.config.sections():
                    if s2.startswith('Profile'):
                        if self.config[s2]['Path'] == default_path:
                            return self.config[s2]['Name']

    def get_path(self, name):
        profile = self.get(name)
        if profile is not None:
            if (bool(profile['IsRelative'])):
                return os.path.join(self.path, profile['Path'])
            return profile['Path']

    def delete(self, name):
        profile = self.get(name, get_section_name=True)
        if profile is not None:
            profile, section = profile
            shutil.rmtree(self.get_path(name))
            del self.config[section]
            self.write()

    def first_startup(self):
        command = 'firefox --headless --no-remote --first-startup'
        p = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        try:
            (stdout, stderr) = p.communicate(timeout=10)
        except subprocess.TimeoutExpired:
            p.kill()
        else:
            if p.returncode != 0:
                raise Exception(stderr)
        self.read()

    def create(self, name, default=True):
        command = 'firefox --headless -no-remote -CreateProfile %s' % name
        p = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        (stdout, stderr) = p.communicate()
        if p.returncode != 0:
            raise Exception(stderr)
        self.read()


def main():
    fields = {
        'name': {'required': False, 'type': 'str'},
        'path': {'default': '~/.mozilla/firefox', 'type': 'str'},
        'state': {
            'default': 'present',
            'choices': ['present', 'absent'],
            'type': 'str',
        },
    }
    module = AnsibleModule(argument_spec=fields)
    profiles = FirefoxProfiles(module.params['path'])
    name = module.params.get('name', None)
    changed = False

    if module.params['state'] == 'present' and name is None:
        default = profiles.get_default()
        if default is None:
            profiles.first_startup()
            changed = True
        name = profiles.get_default()
        path = profiles.get_path(name)
    elif module.params['state'] == 'present' and profiles.get(name) is None:
        profiles.create(name)
        changed = True
        path = profiles.get_path(name)
    elif module.params['state'] == 'absent' and profiles.get(name) is not None:
        path = profiles.get_path(name)
        profiles.delete(name)
        changed = True
    module.exit_json(changed=changed, profile_name=name, profile_path=path)


if __name__ == '__main__':
    main()
