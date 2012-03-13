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

from . import Client, ClientError


class ComputeClient(Client):
    """OpenStack Compute API 1.1 client"""
    
    def raise_for_status(self, r):
        d = r.json
        key = d.keys()[0]
        val = d[key]
        message = '%s: %s' % (key, val.get('message', ''))
        details = val.get('details', '')
        raise ClientError(message, r.status_code, details)
    
    def list_servers(self, detail=False):
        """List servers, returned detailed output if detailed is True"""
        
        path = '/servers/detail' if detail else '/servers'
        r = self.get(path, success=200)
        return r.json['servers']['values']
    
    def get_server_details(self, server_id):
        """Return detailed output on a server specified by its id"""
        
        path = '/servers/%s' % (server_id,)
        r = self.get(path, success=200)
        return r.json['server']
    
    def create_server(self, name, flavor_id, image_id, personality=None):
        """Submit request to create a new server

        The flavor_id specifies the hardware configuration to use,
        the image_id specifies the OS Image to be deployed inside the new
        server.

        The personality argument is a list of (file path, file contents)
        tuples, describing files to be injected into the server upon creation.

        The call returns a dictionary describing the newly created server.
        """
        req = {'server': {'name': name,
                          'flavorRef': flavor_id,
                          'imageRef': image_id}}
        if personality:
            req['personality'] = personality
        
        r = self.post('/servers', json=req, success=202)
        return r.json['server']
    
    def update_server_name(self, server_id, new_name):
        """Update the name of the server as reported by the API.

        This call does not modify the hostname actually used by the server
        internally.
        """
        path = '/servers/%s' % (server_id,)
        req = {'server': {'name': new_name}}
        self.put(path, json=req, success=204)
    
    def delete_server(self, server_id):
        """Submit a deletion request for a server specified by id"""
        
        path = '/servers/%s' % (server_id,)
        self.delete(path, success=204)
    
    def reboot_server(self, server_id, hard=False):
        """Submit a reboot request for a server specified by id"""
        
        path = '/servers/%s/action' % (server_id,)
        type = 'HARD' if hard else 'SOFT'
        req = {'reboot': {'type': type}}
        self.post(path, json=req, success=202)
    
    def get_server_metadata(self, server_id, key=None):
        path = '/servers/%s/meta' % (server_id,)
        if key:
            path += '/%s' % key
        r = self.get(path, success=200)
        return r.json['meta'] if key else r.json['metadata']['values']
    
    def create_server_metadata(self, server_id, key, val):
        path = '/servers/%d/meta/%s' % (server_id, key)
        req = {'meta': {key: val}}
        r = self.put(path, json=req, success=201)
        return r.json['meta']
    
    def update_server_metadata(self, server_id, **metadata):
        path = '/servers/%d/meta' % (server_id,)
        req = {'metadata': metadata}
        r = self.post(path, json=req, success=201)
        return r.json['metadata']
    
    def delete_server_metadata(self, server_id, key):
        path = '/servers/%d/meta/%s' % (server_id, key)
        self.delete(path, success=204)
    
    
    def list_flavors(self, detail=False):
        path = '/flavors/detail' if detail else '/flavors'
        r = self.get(path, success=200)
        return r.json['flavors']['values']

    def get_flavor_details(self, flavor_id):
        path = '/flavors/%d' % flavor_id
        r = self.get(path, success=200)
        return r.json['flavor']
    
    
    def list_images(self, detail=False):
        path = '/images/detail' if detail else '/images'
        r = self.get(path, success=200)
        return r.json['images']['values']
    
    def get_image_details(self, image_id):
        path = '/images/%s' % (image_id,)
        r = self.get(path, success=200)
        return r.json['image']
    
    def delete_image(self, image_id):
        path = '/images/%s' % (image_id,)
        self.delete(path, success=204)

    def get_image_metadata(self, image_id, key=None):
        path = '/images/%s/meta' % (image_id,)
        if key:
            path += '/%s' % key
        r = self.get(path, success=200)
        return r.json['meta'] if key else r.json['metadata']['values']
    
    def create_image_metadata(self, image_id, key, val):
        path = '/images/%s/meta/%s' % (image_id, key)
        req = {'meta': {key: val}}
        r = self.put(path, json=req, success=201)
        return r.json['meta']

    def update_image_metadata(self, image_id, **metadata):
        path = '/images/%s/meta' % (image_id,)
        req = {'metadata': metadata}
        r = self.post(path, json=req, success=201)
        return r.json['metadata']

    def delete_image_metadata(self, image_id, key):
        path = '/images/%s/meta/%s' % (image_id, key)
        self.delete(path, success=204)