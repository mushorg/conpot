# Copyright (C) 2013  Lukas Rist <glaslos@gmail.com>
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc.,
# 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA.


import logging
from datetime import datetime

import gevent.monkey
gevent.monkey.patch_all()

from gevent.wsgi import WSGIServer
from bottle import Bottle, static_file, request, redirect
from jinja2 import Environment, FileSystemLoader, TemplateNotFound

from conpot.snmp import snmp_client


logger = logging.getLogger()
app = Bottle()


class HTTPServer(object):

    def __init__(self, log_queue, http_host="0.0.0.0", http_port=8080, http_path='www/', http_root='index.htm', snmp_port=161):
        self.http_path = http_path
        self.http_root = http_root
        self.host, self.port = http_host, int(http_port)
        self.snmp_host, self.snmp_port = "127.0.0.1", snmp_port
        self.template_env = Environment(loader=FileSystemLoader(self.http_path))
        self._route()
        self.log_queue = log_queue

    def _route(self):
        app.route('/static/<filepath:path>', method="GET", callback=self.server_static)
        app.route(['/', '/index.html', "/<path:path>"], method=["GET", "POST"], callback=self.root_page)
        app.route('/favicon.ico', method="GET", callback=self.favicon)

    def _log(self, request):
        log_dict = {
            'remote': request.remote_addr,
            'timestamp': datetime.utcnow(),
            'data_type': 'http',
            'data': {0: {'request': '{0} {1}'.format(request.method, request.fullpath)}}
        }
        self.log_queue.put(log_dict)

    def server_static(self, filepath):
        return static_file(filepath, root=self.http_path + '/static')

    def favicon(self):
        return None

    def mock_callback(self, sendRequestHandle, errorIndication, errorStatus, errorIndex, varBindTable, cbCtx):
        self.result = None
        if errorIndication:
            self.result = errorIndication
        elif errorStatus:
            self.result = errorStatus.prettyPrint()
        else:
            for oid, val in varBindTable:
                self.result = val.prettyPrint()

    def root_page(self, path='/index.html'):
        logger.info("HTTP request from {0}: {1} {2}".format(request.remote_addr, request.method, request.fullpath))
        self._log(request)
        if not path or path == "/":
            redirect(self.http_root)
        client = snmp_client.SNMPClient(self.snmp_host, self.snmp_port)
        OID = ((1, 3, 6, 1, 2, 1, 1, 1, 0), None)
        client.get_command(OID, callback=self.mock_callback)
        try:
            template = self.template_env.get_template(path)
            return template.render(id=self.result)
        except TemplateNotFound:
            redirect(self.http_root)

    def run(self):
        logger.info('HTTP server started on: {0}'.format((self.host, self.port)))
        try:
            WSGIServer((self.host, self.port), app, log=None).serve_forever()
        except KeyboardInterrupt:
            return 0


if __name__ == '__main__':
    http_server = HTTPServer()
    http_server.run()
