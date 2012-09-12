# Copyright 2011-2012 GRNET S.A. All rights reserved.
#
# Redistribution and use in source and binary forms, with or
# without modification, are permitted provided that the following
# conditions are met:
#
#   1. Redistributions of source code must retain the above
#      copyright notice, this list of conditions and the following
#      disclaimer.
#
#   2. Redistributions in binary form must reproduce the above
#      copyright notice, this list of conditions and the following
#      disclaimer in the documentation and/or other materials
#      provided with the distribution.
#
# THIS SOFTWARE IS PROVIDED BY GRNET S.A. ``AS IS'' AND ANY EXPRESS
# OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
# WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR
# PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL GRNET S.A OR
# CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL,
# SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT
# LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF
# USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED
# AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT
# LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN
# ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
# POSSIBILITY OF SUCH DAMAGE.
#
# The views and conclusions contained in the software and
# documentation are those of the authors and should not be
# interpreted as representing official policies, either expressed
# or implied, of GRNET S.A.

import os

from collections import defaultdict
from ConfigParser import RawConfigParser, NoOptionError, NoSectionError

try:
    from collections import OrderedDict
except ImportError:
    from ordereddict import OrderedDict


# Path to the file that stores the configuration
CONFIG_PATH = os.path.expanduser('~/.kamakirc')

# Name of a shell variable to bypass the CONFIG_PATH value
CONFIG_ENV = 'KAMAKI_CONFIG'

HEADER = """
# Kamaki configuration file
"""

DEFAULTS = {
    'global': {
        'colors': 'on',
        'token': ''
    },
    'config': {
        'cli': 'config_cli',
        'description': 'Configuration commands'
    }
}


class Config(RawConfigParser):
    def __init__(self, path=None):
        RawConfigParser.__init__(self, dict_type=OrderedDict)
        self.path = path or os.environ.get(CONFIG_ENV, CONFIG_PATH)
        self._overrides = defaultdict(dict)
        self._load_defaults()
        self.read(self.path)

    def _load_defaults(self):
        for section, options in DEFAULTS.items():
            for option, val in options.items():
                self.set(section, option, val)

    def apis(self):
        return [api for api in self.sections() if api != 'global']

    def get(self, section, option):
        value = self._overrides.get(section, {}).get(option)
        if value is not None:
            return value

        try:
            return RawConfigParser.get(self, section, option)
        except (NoSectionError, NoOptionError):
            return DEFAULTS.get(section, {}).get(option)

    def set(self, section, option, value):
        if section not in RawConfigParser.sections(self):
            self.add_section(section)
        RawConfigParser.set(self, section, option, value)

    def remove_option(self, section, option):
        try:
            RawConfigParser.remove_option(self, section, option)
        except NoSectionError:
            pass

    def items(self, section, include_defaults=False):
        d = dict(DEFAULTS[section]) if include_defaults else {}
        try:
            d.update(RawConfigParser.items(self, section))
        except NoSectionError:
            pass
        return d.items()

    def override(self, section, option, value):
        self._overrides[section][option] = value

    def write(self):
        with open(self.path, 'w') as f:
            os.chmod(self.path, 0600)
            f.write(HEADER.lstrip())
            RawConfigParser.write(self, f)