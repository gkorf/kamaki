#!/usr/bin/env python

# Copyright 2011 GRNET S.A. All rights reserved.
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

"""
To add a command create a new class and add a 'command' decorator. The class
must have a 'main' method which will contain the code to be executed.
Optionally a command can implement an 'update_parser' class method in order
to add command line arguments, or modify the OptionParser in any way.

The name of the class is important and it will determine the name and grouping
of the command. This behavior can be overriden with the 'group' and 'name'
decorator arguments:

    @command(api='nova')
    class server_list(object):
        # This command will be named 'list' under group 'server'
        ...

    @command(api='nova', name='ls')
    class server_list(object):
        # This command will be named 'ls' under group 'server'
        ...

The docstring of a command class will be used as the command description in
help messages, unless overriden with the 'description' decorator argument.

The syntax of a command will be generated dynamically based on the signature
of the 'main' method, unless overriden with the 'syntax' decorator argument:

    def main(self, server_id, network=None):
        # This syntax of this command will be: '<server id> [network]'
        ...

The order of commands is important, it will be preserved in the help output.
"""

import inspect
import logging
import os
import sys

from base64 import b64encode
from grp import getgrgid
from optparse import OptionParser
from pwd import getpwuid

from kamaki.client import ComputeClient, ImagesClient, ClientError
from kamaki.config import Config, ConfigError
from kamaki.utils import OrderedDict, print_addresses, print_dict, print_items


# Path to the file that stores the configuration
CONFIG_PATH = os.path.expanduser('~/.kamakirc')

# Name of a shell variable to bypass the CONFIG_PATH value
CONFIG_ENV = 'KAMAKI_CONFIG'

# The defaults also determine the allowed keys
CONFIG_DEFAULTS = {
    'apis': 'nova synnefo glance plankton',
    'token': '',
    'compute_url': 'https://okeanos.grnet.gr/api/v1',
    'images_url': 'https://okeanos.grnet.gr/plankton',
}

log = logging.getLogger('kamaki')

_commands = OrderedDict()


def command(api=None, group=None, name=None, description=None, syntax=None):
    """Class decorator that registers a class as a CLI command."""
    
    def decorator(cls):
        grp, sep, cmd = cls.__name__.partition('_')
        if not sep:
            grp, cmd = None, cls.__name__
        
        cls.api = api
        cls.group = group or grp
        cls.name = name or cmd
        cls.description = description or cls.__doc__
        cls.syntax = syntax
        
        if cls.syntax is None:
            # Generate a syntax string based on main's arguments
            spec = inspect.getargspec(cls.main.im_func)
            args = spec.args[1:]
            n = len(args) - len(spec.defaults or ())
            required = ' '.join('<%s>' % x.replace('_', ' ') for x in args[:n])
            optional = ' '.join('[%s]' % x.replace('_', ' ') for x in args[n:])
            cls.syntax = ' '.join(x for x in [required, optional] if x)
        
        if cls.group not in _commands:
            _commands[cls.group] = OrderedDict()
        _commands[cls.group][cls.name] = cls
        return cls
    return decorator


@command()
class config_list(object):
    """list configuration options"""
    
    def main(self):
        for key, val in sorted(self.config.items()):
            print '%s=%s' % (key, val)


@command()
class config_get(object):
    """get a configuration option"""
    
    def main(self, key):
        val = self.config.get(key)
        if val is not None:
            print val


@command()
class config_set(object):
    """set a configuration option"""
    
    def main(self, key, val):
        self.config.set(key, val)


@command()
class config_del(object):
    """delete a configuration option"""
    
    def main(self, key):
        self.config.delete(key)


@command(api='nova')
class server_list(object):
    """list servers"""
    
    @classmethod
    def update_parser(cls, parser):
        parser.add_option('-l', dest='detail', action='store_true',
                default=False, help='show detailed output')
    
    def main(self):
        servers = self.client.list_servers(self.options.detail)
        print_items(servers, self.options.detail)


@command(api='nova')
class server_info(object):
    """get server details"""
    
    def main(self, server_id):
        server = self.client.get_server_details(int(server_id))
        print_dict(server)


@command(api='nova')
class server_create(object):
    """create server"""
    
    @classmethod
    def update_parser(cls, parser):
        parser.add_option('--personality', dest='personalities',
                action='append', default=[],
                metavar='PATH[,SERVER PATH[,OWNER[,GROUP,[MODE]]]]',
                help='add a personality file')
        parser.epilog = "If missing, optional personality values will be " \
                "filled based on the file at PATH if missing."
    
    def main(self, name, flavor_id, image_id):
        personalities = []
        for personality in self.options.personalities:
            p = personality.split(',')
            p.extend([None] * (5 - len(p)))     # Fill missing fields with None
            
            path = p[0]
            
            if not path:
                log.error("Invalid personality argument '%s'", p)
                return 1
            if not os.path.exists(path):
                log.error("File %s does not exist", path)
                return 1
            
            with open(path) as f:
                contents = b64encode(f.read())
            
            st = os.stat(path)
            personalities.append({
                'path': p[1] or os.path.abspath(path),
                'owner': p[2] or getpwuid(st.st_uid).pw_name,
                'group': p[3] or getgrgid(st.st_gid).gr_name,
                'mode': int(p[4]) if p[4] else 0x7777 & st.st_mode,
                'contents': contents})
        
        reply = self.client.create_server(name, int(flavor_id), image_id,
                personalities)
        print_dict(reply)


@command(api='nova')
class server_rename(object):
    """update server name"""
    
    def main(self, server_id, new_name):
        self.client.update_server_name(int(server_id), new_name)


@command(api='nova')
class server_delete(object):
    """delete server"""
    
    def main(self, server_id):
        self.client.delete_server(int(server_id))


@command(api='nova')
class server_reboot(object):
    """reboot server"""
    
    @classmethod
    def update_parser(cls, parser):
        parser.add_option('-f', dest='hard', action='store_true',
                default=False, help='perform a hard reboot')
    
    def main(self, server_id):
        self.client.reboot_server(int(server_id), self.options.hard)


@command(api='synnefo')
class server_start(object):
    """start server"""
    
    def main(self, server_id):
        self.client.start_server(int(server_id))


@command(api='synnefo')
class server_shutdown(object):
    """shutdown server"""
    
    def main(self, server_id):
        self.client.shutdown_server(int(server_id))


@command(api='synnefo')
class server_console(object):
    """get a VNC console"""
    
    def main(self, server_id):
        reply = self.client.get_server_console(int(server_id))
        print_dict(reply)


@command(api='synnefo')
class server_firewall(object):
    """set the firewall profile"""
    
    def main(self, server_id, profile):
        self.client.set_firewall_profile(int(server_id), profile)


@command(api='synnefo')
class server_addr(object):
    """list server addresses"""
    
    def main(self, server_id, network=None):
        reply = self.client.list_server_addresses(int(server_id), network)
        margin = max(len(x['name']) for x in reply)
        print_addresses(reply, margin)


@command(api='nova')
class server_meta(object):
    """get server metadata"""
    
    def main(self, server_id, key=None):
        reply = self.client.get_server_metadata(int(server_id), key)
        print_dict(reply)


@command(api='nova')
class server_addmeta(object):
    """add server metadata"""
    
    def main(self, server_id, key, val):
        reply = self.client.create_server_metadata(int(server_id), key, val)
        print_dict(reply)


@command(api='nova')
class server_setmeta(object):
    """update server metadata"""
    
    def main(self, server_id, key, val):
        metadata = {key: val}
        reply = self.client.update_server_metadata(int(server_id), **metadata)
        print_dict(reply)


@command(api='nova')
class server_delmeta(object):
    """delete server metadata"""
    
    def main(self, server_id, key):
        self.client.delete_server_metadata(int(server_id), key)


@command(api='synnefo')
class server_stats(object):
    """get server statistics"""
    
    def main(self, server_id):
        reply = self.client.get_server_stats(int(server_id))
        print_dict(reply, exclude=('serverRef',))


@command(api='nova')
class flavor_list(object):
    """list flavors"""
    
    @classmethod
    def update_parser(cls, parser):
        parser.add_option('-l', dest='detail', action='store_true',
                default=False, help='show detailed output')
    
    def main(self):
        flavors = self.client.list_flavors(self.options.detail)
        print_items(flavors, self.options.detail)


@command(api='nova')
class flavor_info(object):
    """get flavor details"""
    
    def main(self, flavor_id):
        flavor = self.client.get_flavor_details(int(flavor_id))
        print_dict(flavor)


@command(api='nova')
class image_list(object):
    """list images"""
    
    @classmethod
    def update_parser(cls, parser):
        parser.add_option('-l', dest='detail', action='store_true',
                default=False, help='show detailed output')
    
    def main(self):
        images = self.client.list_images(self.options.detail)
        print_items(images, self.options.detail)


@command(api='nova')
class image_info(object):
    """get image details"""
    
    def main(self, image_id):
        image = self.client.get_image_details(image_id)
        print_dict(image)


@command(api='nova')
class image_create(object):
    """create image"""
    
    def main(self, server_id, name):
        reply = self.client.create_image(int(server_id), name)
        print_dict(reply)


@command(api='nova')
class image_delete(object):
    """delete image"""
    
    def main(self, image_id):
        self.client.delete_image(image_id)


@command(api='nova')
class image_meta(object):
    """get image metadata"""
    
    def main(self, image_id, key=None):
        reply = self.client.get_image_metadata(image_id, key)
        print_dict(reply)


@command(api='nova')
class image_addmeta(object):
    """add image metadata"""
    
    def main(self, image_id, key, val):
        reply = self.client.create_image_metadata(image_id, key, val)
        print_dict(reply)


@command(api='nova')
class image_setmeta(object):
    """update image metadata"""
    
    def main(self, image_id, key, val):
        metadata = {key: val}
        reply = self.client.update_image_metadata(image_id, **metadata)
        print_dict(reply)


@command(api='nova')
class image_delmeta(object):
    """delete image metadata"""
    
    def main(self, image_id, key):
        self.client.delete_image_metadata(image_id, key)


@command(api='synnefo')
class network_list(object):
    """list networks"""
    
    @classmethod
    def update_parser(cls, parser):
        parser.add_option('-l', dest='detail', action='store_true',
                default=False, help='show detailed output')
    
    def main(self):
        networks = self.client.list_networks(self.options.detail)
        print_items(networks, self.options.detail)


@command(api='synnefo')
class network_create(object):
    """create a network"""
    
    def main(self, name):
        reply = self.client.create_network(name)
        print_dict(reply)


@command(api='synnefo')
class network_info(object):
    """get network details"""
    
    def main(self, network_id):
        network = self.client.get_network_details(network_id)
        print_dict(network)


@command(api='synnefo')
class network_rename(object):
    """update network name"""
    
    def main(self, network_id, new_name):
        self.client.update_network_name(network_id, new_name)


@command(api='synnefo')
class network_delete(object):
    """delete a network"""
    
    def main(self, network_id):
        self.client.delete_network(network_id)


@command(api='synnefo')
class network_connect(object):
    """connect a server to a network"""
    
    def main(self, server_id, network_id):
        self.client.connect_server(server_id, network_id)


@command(api='synnefo')
class network_disconnect(object):
    """disconnect a server from a network"""
    
    def main(self, server_id, network_id):
        self.client.disconnect_server(server_id, network_id)


@command(api='glance')
class glance_list(object):
    """list images"""
    
    def main(self):
        images = self.client.list_public()
        print images


def print_groups(groups):
    print
    print 'Groups:'
    for group in groups:
        print '  %s' % group


def print_commands(group, commands):
    print
    print 'Commands:'
    for name, cls in _commands[group].items():
        if name in commands:
            print '  %s %s' % (name.ljust(10), cls.description)


def main():
    parser = OptionParser(add_help_option=False)
    parser.usage = '%prog <group> <command> [options]'
    parser.add_option('--help', dest='help', action='store_true',
            default=False, help='show this help message and exit')
    parser.add_option('--api', dest='apis', metavar='API', action='append',
            help='API to use (can be used multiple times)')
    parser.add_option('--compute-url', dest='compute_url', metavar='URL',
            help='URL for the compute API')
    parser.add_option('--images-url', dest='images_url', metavar='URL',
            help='URL for the images API')
    parser.add_option('--token', dest='token', metavar='TOKEN',
            help='use token TOKEN')
    parser.add_option('-v', dest='verbose', action='store_true', default=False,
            help='use verbose output')
    parser.add_option('-d', dest='debug', action='store_true', default=False,
            help='use debug output')
    
    # Do a preliminary parsing, ignore any errors since we will print help
    # anyway if we don't reach the main parsing.
    _error = parser.error
    parser.error = lambda msg: None
    options, args = parser.parse_args(sys.argv)
    parser.error = _error
    
    if options.debug:
        log.setLevel(logging.DEBUG)
    elif options.verbose:
        log.setLevel(logging.INFO)
    else:
        log.setLevel(logging.WARNING)
    
    try:
        config = Config(CONFIG_PATH, CONFIG_ENV, CONFIG_DEFAULTS)
    except ConfigError, e:
        log.error('%s', e.args[0])
        return 1
    
    for key in CONFIG_DEFAULTS:
        config.override(key, getattr(options, key))
    
    apis = config.get('apis').split()
    
    # Find available groups based on the given APIs
    available_groups = []
    for group, group_commands in _commands.items():
        for name, cls in group_commands.items():
            if cls.api is None or cls.api in apis:
                available_groups.append(group)
                break
    
    if len(args) < 2:
        parser.print_help()
        print_groups(available_groups)
        return 0
    
    group = args[1]
    
    if group not in available_groups:
        parser.print_help()
        print_groups(available_groups)
        return 1
    
    # Find available commands based on the given APIs
    available_commands = []
    for name, cls in _commands[group].items():
        if cls.api is None or cls.api in apis:
            available_commands.append(name)
            continue
    
    parser.usage = '%%prog %s <command> [options]' % group
    
    if len(args) < 3:
        parser.print_help()
        print_commands(group, available_commands)
        return 0
    
    name = args[2]
    
    if name not in available_commands:
        parser.print_help()
        print_commands(group, available_commands)
        return 1
    
    cls = _commands[group][name]
    cls.config = config
    
    syntax = '%s [options]' % cls.syntax if cls.syntax else '[options]'
    parser.usage = '%%prog %s %s %s' % (group, name, syntax)
    parser.epilog = ''
    if hasattr(cls, 'update_parser'):
        cls.update_parser(parser)
    
    options, args = parser.parse_args(sys.argv)
    if options.help:
        parser.print_help()
        return 0
    
    cmd = cls()
    cmd.config = config
    cmd.options = options
    
    if cmd.api in ('nova', 'synnefo'):
        url = config.get('compute_url')
        token = config.get('token')
        cmd.client = ComputeClient(url, token)
    elif cmd.api in ('glance', 'plankton'):
        url = config.get('images_url')
        token = config.get('token')
        cmd.client = ImagesClient(url, token)
    
    try:
        return cmd.main(*args[3:])
    except TypeError:
        parser.print_help()
        return 1
    except ClientError, err:
        log.error('%s', err.message)
        log.info('%s', err.details)
        return 2


if __name__ == '__main__':
    ch = logging.StreamHandler()
    ch.setFormatter(logging.Formatter('%(message)s'))
    log.addHandler(ch)
    err = main() or 0
    sys.exit(err)