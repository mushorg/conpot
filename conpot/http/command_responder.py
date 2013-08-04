# Copyright (C) 2013  Daniel creo Haslinger <creo-conpot@blackmesa.at>
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
import time

from datetime import datetime

from HTMLParser import HTMLParser
from SocketServer import ThreadingMixIn
import gevent.monkey
gevent.monkey.patch_all()

import BaseHTTPServer
import httplib
from lxml import etree

from conpot.snmp import snmp_client

logger = logging.getLogger()


class HTTPServer(BaseHTTPServer.BaseHTTPRequestHandler):

    def log(self, version, request_type, addr, request, response=None):

        log_dict = {'remote': addr,
                    'timestamp': datetime.utcnow(),
                    'data_type': 'http',
                    'data': {0: {'request': '{0} {1}: {2}'.format(version, request_type, request)}}}

        logger.info('{0} {1} request from {2}: {3}'.format(version, request_type, addr, request))

        if response:
            logger.info('{0} response to {1}: {2}'.format(version, addr, response))
            log_dict['data'][0]['response'] = '{0} response: {1}'.format(version, response)

        self.server.log_queue.put(log_dict)

    def get_entity_headers(self, rqfilename, headers, configuration):

        xml_headers = configuration.xpath('//conpot_template/http/htdocs/node[@name="' + rqfilename + '"]/headers/*')

        if xml_headers:

            # retrieve all headers assigned to this entity
            for header in xml_headers:
                headers.append((header.attrib['name'], header.text))

        return headers

    def get_status_headers(self, status, headers, configuration):

        xml_headers = configuration.xpath('//conpot_template/http/statuscodes/status[@name="' +
                                          str(status) + '"]/headers/*')

        if xml_headers:

            # retrieve all headers assigned to this status
            for header in xml_headers:
                headers.append((header.attrib['name'], header.text))

        return headers

    def send_response(self, code, message=None):
        """Send the response header and log the response code.
        This function is overloaded to change the behaviour when
        logging and sending default headers.
        """

        # replace integrated logging with conpot logger..
        # self.log_request(code)

        if message is None:
            if code in self.responses:
                message = self.responses[code][0]
            else:
                message = ''

        if self.request_version != 'HTTP/0.9':
            self.wfile.write("%s %d %s\r\n" %
                             (self.protocol_version, code, message))

        # the following two headers are omitted, which is why we override
        # send_response() at all. We do this one on our own...

        #self.send_header('Server', self.version_string())
        #self.send_header('Date', self.date_time_string())

    def substitute_template_fields(self, payload):

        # initialize parser with our payload
        parser = TemplateParser(payload, self.server.snmp_host, self.server.snmp_port)

        # triggers the parser, just in case of open / incomplete tags..
        parser.close()

        # retrieve and return (substituted) payload
        return parser.payload

    def load_status(self, status, requeststring, headers, configuration, docpath):
        """Retrieves headers and payload for a given status code.
           Certain status codes can be configured to forward the
           request to a remote system. If not available, generate
           a minimal response"""

        source = 'filesystem'

        # handle PROXY tag
        entity_proxy = configuration.xpath('//conpot_template/http/statuscodes/status[@name="' +
                                           str(status) +
                                           '"]/proxy')

        if entity_proxy:
            source = 'proxy'
            target = entity_proxy[0].xpath('./text()')[0]

        # the requested resource resides on our filesystem,
        # so we try retrieve all metadata and the resource itself from there.

        if source == 'filesystem':

            # retrieve headers from entities configuration block
            headers = self.get_status_headers(status, headers, configuration)

            # retrieve payload directly from filesystem, if possible.
            # If this is not possible, return an empty, zero sized string.
            try:
                with open(docpath + '/statuscodes/' + str(status) + '.status', 'rb') as f:
                    payload = f.read()

            except IOError:
                payload = ''

            # there might be template data that can be substituted within the
            # payload. We only substitute data that is going to be displayed
            # by the browser:

            # perform template substitution on payload
            payload = self.substitute_template_fields(payload)

            # Calculate and append a content length header
            headers.append(('Content-Length', payload.__len__()))

            return status, headers, payload

        # the requested status code is configured to forward the
        # originally targetted resource to a remote system.

        elif source == 'proxy':

            # open a connection to the remote system.
            # If something goes wrong, fall back to 503.

            # NOTE: we use try:except here because there is no perfect
            # platform independent way to check file accessibility.

            try:

                conn = httplib.HTTPConnection(target)
                conn.request("GET", requeststring)
                response = conn.getresponse()

                status = int(response.status)
                headers = response.getheaders()   # We REPLACE the headers to avoid duplicates!
                payload = response.read()

                # WORKAROUND: to get around a strange httplib-behaviour when it comes
                # to chunked transfer encoding, we replace the chunked-header with a
                # valid Content-Length header:

                for i, header in enumerate(headers):

                    if header[0].lower() == 'transfer-encoding' and header[1].lower() == 'chunked':
                        del headers[i]
                        break

            except:

                # before falling back to 503, we check if we are ALREADY dealing with a 503
                # to prevent an infinite request handling loop...

                if status != 503:

                    # we're handling another error here.
                    # generate a 503 response from configuration.
                    (status, headers, payload) = self.load_status(status,
                                                                  requeststring,
                                                                  headers,
                                                                  configuration,
                                                                  docpath)

                else:

                    # oops, we're heading towards an infinite loop here,
                    # generate a minimal 503 response regardless of the configuration.
                    status = 503
                    payload = ''
                    headers.append(('Content-Length', 0))

            return status, headers, payload

    def load_entity(self, requeststring, headers, configuration, docpath):
        """
        Retrieves status, headers and payload for a given entity, that
        can be stored either local or on a remote system
        """

        source = 'filesystem'

        # extract filename and GET parameters from request string
        rqfilename = requeststring.partition('?')[0]
        rqparams = requeststring.partition('?')[2]

        # handle ALIAS tag
        entity_alias = configuration.xpath('//conpot_template/http/htdocs/node[@name="' + rqfilename + '"]/alias')
        if entity_alias:
            rqfilename = entity_alias[0].xpath('./text()')[0]

        # handle PROXY tag
        entity_proxy = configuration.xpath('//conpot_template/http/htdocs/node[@name="' + rqfilename + '"]/proxy')
        if entity_proxy:
            source = 'proxy'
            target = entity_proxy[0].xpath('./text()')[0]

        # the requested resource resides on our filesystem,
        # so we try retrieve all metadata and the resource itself from there.

        if source == 'filesystem':

            # handle STATUS tag
            # ( filesystem only, since proxied requests come with their own status )
            entity_status = configuration.xpath('//conpot_template/http/htdocs/node[@name="' + rqfilename + '"]/status')
            if entity_status:
                status = int(entity_status[0].xpath('./text()')[0])
            else:
                status = 200

            # retrieve headers from entities configuration block
            headers = self.get_entity_headers(rqfilename, headers, configuration)

            # retrieve payload directly from filesystem, if possible.
            # If this is not possible, return an empty, zero sized string.
            try:
                with open(docpath + '/htdocs/' + rqfilename, 'rb') as f:
                    payload = f.read()

            except IOError:
                payload = ''

            # there might be template data that can be substituted within the
            # payload. We only substitute data that is going to be displayed
            # by the browser:

            templated = False
            for header in headers:
                if header[0].lower() == 'content-type' and header[1].lower() == 'text/html':
                    templated = True

            if templated:
                # perform template substitution on payload
                payload = self.substitute_template_fields(payload)

            # Calculate and append a content length header
            headers.append(('Content-Length', payload.__len__()))

            return status, headers, payload

        # the requested resource resides on another server,
        # so we act as a proxy between client and target system

        elif source == 'proxy':

            # open a connection to the remote system.
            # If something goes wrong, fall back to 503

            try:
                conn = httplib.HTTPConnection(target)
                conn.request("GET", requeststring)
                response = conn.getresponse()

                status = int(response.status)
                headers = response.getheaders()    # We REPLACE the headers to avoid duplicates!
                payload = response.read()

            except:
                status = 503
                (status, headers, payload) = self.load_status(status, requeststring, headers, configuration, docpath)

            return status, headers, payload

    def send_error(self, code, message=None):
        """Send and log an error reply.
        This method is overloaded to make use of load_status()
        to allow handling of "Unsupported Method" errors.
        """

        headers = []
        headers.extend(self.server.global_headers)
        configuration = self.server.configuration
        docpath = self.server.docpath

        trace_data_length = self.headers.getheader('content-length')
        unsupported_request_data = None

        if trace_data_length:
            unsupported_request_data = self.rfile.read(int(trace_data_length))

        # there are certain situations where variables are (not yet) registered
        # ( e.g. corrupted request syntax ). In this case, we set them manually.
        if hasattr(self, 'path'):
            requeststring = self.path
        else:
            requeststring = ''

        # generate the appropriate status code, header and payload
        (status, headers, payload) = self.load_status(code,
                                                      requeststring.partition('?')[0],
                                                      headers,
                                                      configuration,
                                                      docpath)

        # send http status to client
        self.send_response(status)

        # send all headers to client
        for header in headers:
            self.send_header(header[0], header[1])

        self.end_headers()

        # send payload (the actual content) to client
        self.wfile.write(payload)

        # logging
        self.log(self.request_version, self.command, self.client_address, (self.path,
                                                                           self.headers.headers,
                                                                           unsupported_request_data), status)

    def do_TRACE(self):
        """Handle TRACE requests."""

        # fetch configuration dependend variables from server instance
        headers = []
        headers.extend(self.server.global_headers)
        configuration = self.server.configuration
        docpath = self.server.docpath

        # retrieve TRACE body data
        # ( sticking to the HTTP protocol, there should not be any body in TRACE requests,
        #   an attacker could though use the body to inject data if not flushed correctly,
        #   which is done by accessing the data like we do now - just to be secure.. )

        trace_data_length = self.headers.getheader('content-length')
        trace_data = None

        if trace_data_length:
            trace_data = self.rfile.read(int(trace_data_length))

        # check configuration: are we allowed to use this method?
        if self.server.disable_method_trace is True:

            # Method disabled by configuration. Fall back to 501.
            status = 501
            (status, headers, payload) = self.load_status(status, self.path, headers, configuration, docpath)
            
        else:

            # Method is enabled
            status = 200
            payload = ''
            headers.append(('Content-Type', 'message/http'))

            # Gather all request data and return it to sender..
            for rqheader in self.headers:
                payload = payload + str(rqheader) + ': ' + self.headers.get(rqheader) + "\n"

        # send initial HTTP status line to client
        self.send_response(status)

        # send all headers to client
        for header in headers:
            self.send_header(header[0], header[1])

        self.end_headers()

        # send payload (the actual content) to client
        self.wfile.write(payload)

        # logging
        self.log(self.request_version,
                 self.command,
                 self.client_address,
                 (self.path, self.headers.headers, trace_data),
                 status)

    def do_HEAD(self):
        """Handle HEAD requests."""

        # fetch configuration dependend variables from server instance
        headers = []
        headers.extend(self.server.global_headers)
        configuration = self.server.configuration
        docpath = self.server.docpath

        # retrieve HEAD body data
        # ( sticking to the HTTP protocol, there should not be any body in HEAD requests,
        #   an attacker could though use the body to inject data if not flushed correctly,
        #   which is done by accessing the data like we do now - just to be secure.. )

        head_data_length = self.headers.getheader('content-length')
        head_data = None

        if head_data_length:
            head_data = self.rfile.read(int(head_data_length))

        # check configuration: are we allowed to use this method?
        if self.server.disable_method_head is True:

            # Method disabled by configuration. Fall back to 501.
            status = 501
            (status, headers, payload) = self.load_status(status, self.path, headers, configuration, docpath)
            
        else:

            # try to find a configuration item for this GET request
            entity_xml = configuration.xpath('//conpot_template/http/htdocs/node[@name="' +
                                             self.path.partition('?')[0] + '"]')

            if entity_xml:
                # A config item exists for this entity. Handle it..
                (status, headers, payload) = self.load_entity(self.path, headers, configuration, docpath)

            else:
                # No config item could be found. Fall back to a standard 404..
                status = 404
                (status, headers, payload) = self.load_status(status, self.path, headers, configuration, docpath)

        # send initial HTTP status line to client
        self.send_response(status)

        # send all headers to client
        for header in headers:
            self.send_header(header[0], header[1])

        self.end_headers()

        # logging
        self.log(self.request_version,
                 self.command,
                 self.client_address,
                 (self.path, self.headers.headers, head_data),
                 status)

    def do_GET(self):
        """Handle GET requests"""

        # fetch configuration dependend variables from server instance
        headers = []
        headers.extend(self.server.global_headers)
        configuration = self.server.configuration
        docpath = self.server.docpath

        # retrieve GET body data
        # ( sticking to the HTTP protocol, there should not be any body in GET requests,
        #   an attacker could though use the body to inject data if not flushed correctly,
        #   which is done by accessing the data like we do now - just to be secure.. )

        get_data_length = self.headers.getheader('content-length')
        get_data = None

        if get_data_length:
            get_data = self.rfile.read(int(get_data_length))

        # try to find a configuration item for this GET request
        entity_xml = configuration.xpath('//conpot_template/http/htdocs/node[@name="' +
                                         self.path.partition('?')[0] + '"]')

        if entity_xml:
            # A config item exists for this entity. Handle it..
            (status, headers, payload) = self.load_entity(self.path, headers, configuration, docpath)

        else:
            # No config item could be found. Fall back to a standard 404..
            status = 404
            (status, headers, payload) = self.load_status(status, self.path, headers, configuration, docpath)

        # send initial HTTP status line to client
        self.send_response(status)

        # send all headers to client
        for header in headers:
            self.send_header(header[0], header[1])

        self.end_headers()

        # send payload (the actual content) to client
        self.wfile.write(payload)

        # logging
        self.log(self.request_version,
                 self.command,
                 self.client_address,
                 (self.path, self.headers.headers, get_data),
                 status)

    def do_POST(self):
        """Handle POST requests"""

        # fetch configuration dependend variables from server instance
        headers = []
        headers.extend(self.server.global_headers)
        configuration = self.server.configuration
        docpath = self.server.docpath

        # retrieve POST data ( important to flush request buffers )
        post_data_length = self.headers.getheader('content-length')
        post_data = None

        if post_data_length:
            post_data = self.rfile.read(int(post_data_length))

        # try to find a configuration item for this POST request
        entity_xml = configuration.xpath('//conpot_template/http/htdocs/node[@name="' +
                                         self.path.partition('?')[0] + '"]')

        if entity_xml:
            # A config item exists for this entity. Handle it..
            (status, headers, payload) = self.load_entity(self.path, headers, configuration, docpath)

        else:
            # No config item could be found. Fall back to a standard 404..
            status = 404
            (status, headers, payload) = self.load_status(status, self.path, headers, configuration, docpath)

        # send initial HTTP status line to client
        self.send_response(status)

        # send all headers to client
        for header in headers:
            self.send_header(header[0], header[1])

        self.end_headers()

        # send payload (the actual content) to client
        self.wfile.write(payload)

        # logging
        self.log(self.request_version,
                 self.command,
                 self.client_address,
                 (self.path, self.headers.headers, post_data),
                 status)


class TemplateParser(HTMLParser):

    def __init__(self, data, snmp_host, snmp_port):
        
        HTMLParser.__init__(self)

        self.payload = data
        self.snmp_host = snmp_host
        self.snmp_port = snmp_port

        self.feed(data)

    def mock_snmp_callback(self, sendRequestHandle, errorIndication, errorStatus, errorIndex, varBindTable, cbCtx):
        self.result = None
        if errorIndication:
            self.result = errorIndication
        elif errorStatus:
            self.result = errorStatus.prettyPrint()
        else:
            for oid, val in varBindTable:
                self.result = val.prettyPrint()

    def handle_startendtag(self, tag, attrs):
        """ handles template tags provided in XHTML notation.

            Expected format:    <condata source="(engine)" key="(descriptor)" />
            Example:            <condata source="snmp" key="1.3.6.1.2.1.1.1" />

            at the moment, the parser is space- and case-sensitive(!),
            this could be improved by using REGEX for replacing the template tags
            with actual values.
        """

        source = ''
        key = ''

        # only parse tags that are conpot template tags ( <condata /> )
        if tag == 'condata':

            # initialize original tag (needed for value replacement)
            origin = '<' + tag

            for attribute in attrs:

                # extend original tag
                origin = origin + ' ' + attribute[0] + '="' + attribute[1] + '"'

                # fill variables with all meta information needed to
                # gather actual data from the other engines (snmp, modbus, ..)
                if attribute[0] == 'source':
                    source = attribute[1]
                elif attribute[0] == 'key':
                    key = attribute[1]

            # finalize original tag
            origin += ' />'

            # we really need a key in order to do our work..
            if key:

                # deal with snmp powered tags:
                if source == 'snmp':

                    # initialize snmp client
                    client = snmp_client.SNMPClient(self.snmp_host, self.snmp_port)

                    # convert key to (int-)tuple filled OID descriptor
                    key = key.split('.')
                    key = (tuple(map(int, key)), None)
                    client.get_command(key, callback=self.mock_snmp_callback)

                    self.payload = self.payload.replace(origin, self.result)

                # deal with eval powered tags:
                elif source == 'eval':

                    result = ''

                    # evaluate key
                    try:
                        result = eval(key)
                    except:
                        pass

                    self.payload = self.payload.replace(origin, result)


class ThreadedHTTPServer(ThreadingMixIn, BaseHTTPServer.HTTPServer):
    """Handle requests in a separate thread."""


class SubHTTPServer(ThreadedHTTPServer):
    """this class is necessary to allow passing custom request handler into
       the RequestHandlerClass"""

    def __init__(self, server_address, RequestHandlerClass, template, docpath, snmp_host, snmp_port, log_queue):
        BaseHTTPServer.HTTPServer.__init__(self, server_address, RequestHandlerClass)

        self.docpath = docpath
        self.snmp_host = snmp_host
        self.snmp_port = snmp_port
        self.log_queue = log_queue

        # default configuration
        self.update_header_date = True              # this preserves authenticity
        self.disable_method_head = True            # considered to be safe
        self.disable_method_trace = True            # considered to be unsafe

        # load the configuration from template and parse it
        # for the first time in order to reduce further handling..
        self.configuration = etree.parse(template)

        xml_config = self.configuration.xpath('//conpot_template/http/global/config/*')
        if xml_config:

            # retrieve all headers assigned to this status code
            for entity in xml_config:

                if entity.attrib['name'] == 'protocol_version':
                    RequestHandlerClass.protocol_version = entity.text

                elif entity.attrib['name'] == 'update_header_date':
                    if entity.text.lower() == 'false':
                        self.update_header_date = False
                        # DATE header auto update disabled by configuration ( default: enabled )
                    else:
                        self.update_header_date = True
                        # DATE header auto update enabled by configuration ( default: enabled )

                elif entity.attrib['name'] == 'disable_method_head':
                    if entity.text.lower() == 'true':
                        self.disable_method_head = True
                        # HEAD method disabled by configuration ( default: enabled )
                    else:
                        self.disable_method_head = False
                        # HEAD method enabled by configuration ( default: enabled )

                elif entity.attrib['name'] == 'disable_method_trace':
                    if entity.text.lower() == 'false':
                        self.disable_method_trace = False
                        # TRACE method enabled by configuration ( default: enabled )
                    else:
                        self.disable_method_trace = True
                        # TRACE method disabled by configuration ( default: enabled )

        # load global headers from XML
        self.global_headers = []
        xml_headers = self.configuration.xpath('//conpot_template/http/global/headers/*')
        if xml_headers:

            # retrieve all headers assigned to this status code
            for header in xml_headers:
                if header.attrib['name'].lower() == 'date' and self.update_header_date is True:
                    # All HTTP date/time stamps MUST be represented in Greenwich Mean Time (GMT),
                    # without exception ( RFC-2616 )
                    self.global_headers.append((header.attrib['name'],
                                                time.strftime('%a, %d %b %Y %H:%M:%S GMT', time.gmtime())))
                else:
                    self.global_headers.append((header.attrib['name'], header.text))


class CommandResponder(object):

    def __init__(self, host, port, template, log_queue, docpath, snmp_host, snmp_port):

        self.log_queue = log_queue

        # Create HTTP server class
        self.httpd = SubHTTPServer((host, port), HTTPServer, template, docpath, snmp_host, snmp_port, log_queue)

    def serve_forever(self):
        self.httpd.serve_forever()

    def stop(self):
        logging.info("HTTP server will shut down gracefully as soon as all connections are closed.")
        self.httpd.shutdown()


if __name__ == '__main__':
    http_server = HTTPServer()
    http_server.run()
