import logging
from datetime import datetime
from pprint import pprint

import gevent.monkey
gevent.monkey.patch_all()

from gevent.wsgi import WSGIServer
from bottle import Bottle, static_file, request
from jinja2 import Environment, FileSystemLoader, TemplateNotFound

from conpot.snmp import snmp_client


logger = logging.getLogger()
app = Bottle()


class HTTPServer(object):

    def __init__(self, log_queue, www_host="0.0.0.0", www_port=8080, www_path="./www", snmp_port=161):
        self.www_path = www_path
        self.host, self.port = www_host, int(www_port)
        self.snmp_host, self.snmp_port = "127.0.0.1", snmp_port
        self.template_env = Environment(loader=FileSystemLoader(www_path))
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
        return static_file(filepath, root=self.www_path + '/static')

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

    def root_page(self, path=None):
        logger.info("HTTP request from {0}: {1} {2}".format(request.remote_addr, request.method, request.fullpath))
        self._log(request)
        if not path or path == "/":
            path = "index.html"
        client = snmp_client.SNMPClient(self.snmp_host, self.snmp_port)
        OID = ((1, 3, 6, 1, 2, 1, 1, 1, 0), None)
        client.get_command(OID, callback=self.mock_callback)
        try:
            template = self.template_env.get_template(path)
        except TemplateNotFound:
            template = self.template_env.get_template("index.html")
        return template.render(id=self.result)

    def run(self):
        logger.info('HTTP server started on: {0}'.format((self.host, self.port)))
        try:
            WSGIServer((self.host, self.port), app, log=None).serve_forever()
        except KeyboardInterrupt:
            return 0


if __name__ == '__main__':
    http_server = HTTPServer()
    http_server.run()