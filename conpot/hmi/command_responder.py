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

import threading
import logging

from time import *
from datetime import datetime
from pprint import pprint

from HTMLParser import HTMLParser
from SocketServer import ThreadingMixIn
import gevent.monkey
gevent.monkey.patch_all()

import BaseHTTPServer, httplib
from lxml import etree

from conpot.snmp import snmp_client

logger = logging.getLogger()


class HTTPServer(BaseHTTPServer.BaseHTTPRequestHandler):




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
        if trace_data_length:
            trace_data = self.rfile.read(int(trace_data_length))
            if trace_data:
                print "HMI:DEBUG: *** PROTOCOL ANOMALY *** TRACE request carried payload: {0}".format(trace_data)


        # check configuration: are we allowed to use this method?
        if self.server.disable_method_trace is True:

            # Method disabled by configuration. Fall back to 501.
            status = 501
            print "HMI:DEBUG: requested method disabled by configuration. falling back to http status 501"
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
        logger.info("{0} {1} response to {2}: {3} ( no payload )".format(self.request_version, self.command, self.client_address, status))



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
        if head_data_length:
            head_data = self.rfile.read(int(head_data_length))
            if head_data:
                print "HMI:DEBUG: *** PROTOCOL ANOMALY *** HEAD request carried payload: {0}".format(head_data)


        # check configuration: are we allowed to use this method?
        if self.server.disable_method_head is True:

            # Method disabled by configuration. Fall back to 501.
            status = 501
            print "HMI:DEBUG: requested method disabled by configuration. falling back to http status 501"
            (status, headers, payload) = self.load_status(status, self.path, headers, configuration, docpath)
            
        else:

            # try to find a configuration item for this GET request
            entity_xml = configuration.xpath('//conpot_template/hmi/htdocs/node[@name="'+self.path.partition('?')[0]+'"]')

            if entity_xml:
                # A config item exists for this entity. Handle it..
                (status, headers, payload) = self.load_entity(self.path, headers, configuration, docpath)

            else:
                # No config item could be found. Fall back to a standard 404..
                status = 404
                (status, headers, payload) = self.load_status(status, self.path, headers, configuration, docpath)
                print "HMI:DEBUG: requested entity not found. falling back to http status 404"

        
        # send initial HTTP status line to client
        self.send_response(status)

        # send all headers to client
        for header in headers:
            self.send_header(header[0], header[1])

        self.end_headers()

        # logging
        logger.info("{0} {1} response to {2}: {3} ( no payload )".format(self.request_version, self.command, self.client_address, status))



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
        if get_data_length:
            get_data = self.rfile.read(int(get_data_length))
            if get_data:
                print "HMI:DEBUG: *** PROTOCOL ANOMALY *** GET request carried payload: {0}".format(get_data)

        # try to find a configuration item for this GET request
        entity_xml = configuration.xpath('//conpot_template/hmi/htdocs/node[@name="'+self.path.partition('?')[0]+'"]')

        if entity_xml:
            # A config item exists for this entity. Handle it..
            (status, headers, payload) = self.load_entity(self.path, headers, configuration, docpath)

        else:
            # No config item could be found. Fall back to a standard 404..
            status = 404
            print "HMI:DEBUG: requested entity not found. falling back to http status 404"
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
        logger.info("{0} {1} response to {2}: {3} ( {4} bytes payload )".format(self.request_version, self.command, self.client_address, status, payload.__len__()))



    def do_POST(self):
        """Handle POST requests"""

        # fetch configuration dependend variables from server instance
        headers = []
        headers.extend(self.server.global_headers)
        configuration = self.server.configuration
        docpath = self.server.docpath

        # retrieve POST data ( important to flush request buffers )
        post_data_length = self.headers.getheader('content-length')
        if post_data_length:
            post_data = self.rfile.read(int(post_data_length))
            if post_data:
                print "HMI:DEBUG: POST request carried payload: {0}".format(post_data)

        # try to find a configuration item for this POST request
        entity_xml = configuration.xpath('//conpot_template/hmi/htdocs/node[@name="'+self.path.partition('?')[0]+'"]')

        if entity_xml:
            # A config item exists for this entity. Handle it..
            (status, headers, payload) = self.load_entity(self.path, headers, configuration, docpath)

        else:
            # No config item could be found. Fall back to a standard 404..
            status = 404
            print "HMI:DEBUG: requested entity not found. falling back to http status 404"
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
        logger.info("{0} {1} response to {2}: {3} ( {4} bytes payload )".format(self.request_version, self.command, self.client_address, status, payload.__len__()))



    def substitute_template_fields(self, payload):

        print "HMI:DEBUG: parsing response payload"

        # initialize parser with our payload
        parser = TemplateParser(payload, self.server.snmp_host, self.server.snmp_port)

        # triggers the parser, just in case of open / incomplete tags..
        parser.close()

        # retrieve and return (substituted) payload
        return parser.payload




    def load_entity(self, requeststring, headers, configuration, docpath):
        """Retrieves status, headers and payload for a given entity, that
           can be stored either local or on a remote system"""

        source = 'filesystem'

        # extract filename and GET parameters from request string
        rqfilename = requeststring.partition('?')[0]
        rqparams = requeststring.partition('?')[2]


        # handle ALIAS tag
        entity_alias = configuration.xpath('//conpot_template/hmi/htdocs/node[@name="'+rqfilename+'"]/alias')
        if entity_alias:
            rqfilename = entity_alias[0].xpath('./text()')[0]
            print "HMI:DEBUG: requested entity is an alias to "+rqfilename

        # handle PROXY tag
        entity_proxy = configuration.xpath('//conpot_template/hmi/htdocs/node[@name="'+rqfilename+'"]/proxy')
        if entity_proxy:
            source = 'proxy'
            target = entity_proxy[0].xpath('./text()')[0]
            print "HMI:DEBUG: requested entity is proxied to "+target



        # the requested resource resides on our filesystem,
        # so we try retrieve all metadata and the resource itself from there.

        if source == 'filesystem':

            # handle STATUS tag
            # ( filesystem only, since proxied requests come with their own status )
            entity_status = configuration.xpath('//conpot_template/hmi/htdocs/node[@name="'+rqfilename+'"]/status')
            if entity_status:
                status = int(entity_status[0].xpath('./text()')[0])
            else:
                status = 200


            # retrieve headers from entities configuration block
            headers = self.get_entity_headers(rqfilename, headers, configuration)


            # retrieve payload directly from filesystem, if possible.
            # If this is not possible, return an empty, zero sized string.
            try:
                f = open(docpath+'/htdocs/'+rqfilename, 'r')
                payload = f.read()
                f.close()
            except IOError:
                print "HMI:DEBUG: could not retrieve "+rqfilename+" from filesytem. Replying with empty payload."
                payload = ''


            # there might be template data that can be substituted within the
            # payload. We only substitute data that is going to be displayed
            # by the browser:

            templated=0
            for header in headers:
                if header[0].lower() == 'content-type' and header[1].lower() == 'text/html':
                    templated=1

            if templated == 1: 
                # perform template substitution on payload
                payload = self.substitute_template_fields(payload)


            # Calculate and append a content length header
            headers.append(('Content-Length', payload.__len__()))


            return (status, headers, payload)


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
                headers = response.getheaders() # We REPLACE the headers to avoid duplicates!
                payload = response.read()

            except:
                status = 503
                print "HMI:DEBUG: could not retrieve "+rqfilename+" from proxy. Falling back to 503."
                (status, headers, payload) = self.load_status(status, requeststring, headers, configuration, docpath)



            return (status, headers, payload)



    def get_entity_headers(self, rqfilename, headers, configuration):

        xml_headers = configuration.xpath('//conpot_template/hmi/htdocs/node[@name="'+rqfilename+'"]/headers/*')

        if xml_headers:

            # retrieve all headers assigned to this entity
            for header in xml_headers:
                headers.append((header.attrib['name'], header.text))

        return headers



    def send_error(self, code, message=None):
        """Send and log an error reply.

        This method is overloaded to make use of load_status()
        to allow handling of "Unsupported Method" errors.

        """

        headers = []
        headers.extend(self.server.global_headers)
        configuration = self.server.configuration
        docpath = self.server.docpath

        print "HMI:DEBUG: Method not implemented (yet). Falling back to 501."

        
        # there are certain situations where variables are (not yet) registered
        # ( e.g. corrupted request syntax ). In this case, we set them manually.
        if hasattr(self, 'path'):
            requeststring = self.path
        else:
            requeststring = ''


        # generate the appropriate status code, header and payload
        (status, headers, payload) = self.load_status(code, requeststring.partition('?')[0], headers, configuration, docpath)

        # send http status to client
        self.send_response(status)
        
        # send all headers to client
        for header in headers:
            self.send_header(header[0], header[1])

        self.end_headers()

        # send payload (the actual content) to client
        self.wfile.write(payload)

        # logging
        logger.info("{0} {1} response to {2}: {3} ( {4} bytes payload )".format(self.request_version, self.command, self.client_address, status, payload.__len__()))



    def load_status(self, status, requeststring, headers, configuration, docpath):
        """Retrieves headers and payload for a given status code.
           Certain status codes can be configured to forward the
           request to a remote system. If not available, generate
           a minimal response"""


        source = 'filesystem'

        # extract filename and GET parameters from request string
        rqfilename = requeststring.partition('?')[0]
        rqparams = requeststring.partition('?')[2]

        # handle PROXY tag
        entity_proxy = configuration.xpath('//conpot_template/hmi/statuscodes/status[@name="'+str(status)+'"]/proxy')
        if entity_proxy:
            source = 'proxy'
            target = entity_proxy[0].xpath('./text()')[0]
            print "HMI:DEBUG: requested status "+str(status)+" is proxied to "+target




        # the requested resource resides on our filesystem,
        # so we try retrieve all metadata and the resource itself from there.

        if source == 'filesystem':

            # retrieve headers from entities configuration block
            headers = self.get_status_headers(status, headers, configuration)


            # retrieve payload directly from filesystem, if possible.
            # If this is not possible, return an empty, zero sized string.
            try:
                f = open(docpath+'/statuscodes/'+str(status)+'.status', 'r')
                payload = f.read()
                f.close()
            except IOError:
                payload = ''
                print "HMI:DEBUG: could not load '"+str(status)+".status' from filesystem. Replying with empty payload."

            # Calculate and append a content length header
            headers.append(('Content-Length', payload.__len__()))


            return (status, headers, payload)


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
                headers = response.getheaders() # We REPLACE the headers to avoid duplicates!
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
                    print "HMI:DEBUG: could not load status "+str(status)+" from proxy. Falling back to 503."
                    (status, headers, payload) = self.load_status(status, requeststring, headers, configuration, docpath)

                else:

                    # oops, we're heading towards an infinite loop here,
                    # generate a minimal 503 response regardless of the configuration.
                    status = 503
                    payload = ''
                    headers.append(('Content-Length', 0))
                    print "HMI:DEBUG: could not load status "+str(status)+" from proxy. Loop prevention: Falling back to minimal 503."


            return (status, headers, payload)



    def get_status_headers(self, status, headers, configuration):

        xml_headers = configuration.xpath('//conpot_template/hmi/statuscodes/status[@name="'+str(status)+'"]/headers/*')

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
        #self.log_request(code)
        
        if message is None:
            if code in self.responses:
                message = self.responses[code][0]
            else:
                message = ''

        if self.request_version != 'HTTP/0.9':
            self.wfile.write("%s %d %s\r\n" %
                             (self.protocol_version, code, message))

        # there are certain situations where variables are (not yet) registered
        # ( e.g. corrupted request syntax ). In this case, we set them manually.
        if hasattr(self, 'path'):
            requeststring = self.path
        else:
            requeststring = ''

        logger.info("{0} {1} request from {2}: {3}".format(self.request_version, self.command, self.client_address, requeststring.partition('?')[0]))

        # the following two headers are omitted, which is why we override
        # send_response() at all. We do this one on our own...

        #self.send_header('Server', self.version_string())
        #self.send_header('Date', self.date_time_string())



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
            self.result = errorStatus.prettyPrint();
        else:
            for oid, val in varBindTable:
                self.result = val.prettyPrint();
        

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

            print "HMI:DEBUG: template tag found: {0} - {1}".format(tag, attrs)

            # initialize original tag (needed for value replacement)
            origin = '<'+tag

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
            origin = origin + ' />'
            print "HMI:DEBUG: template restored original tag: "+origin 


            # we really need a key in order to do our work..
            if not key:

                    print "HMI:DEBUG: could not substitute tag (key missing)"

            else:

                # deal with snmp powered tags:
                if source == 'snmp':

                    # initialize snmp client
                    client = snmp_client.SNMPClient(self.snmp_host, self.snmp_port)

                    # convert key to (int-)tuple filled OID descriptor
                    key = key.split('.')
                    key = (tuple(map(int, key)), None)
                    client.get_command(key, callback=self.mock_snmp_callback)
                    print "HMI:DEBUG: template retrieved SNMP value: {0}".format(self.result)

                    self.payload = self.payload.replace(origin, self.result)

                # deal with eval powered tags:
                elif source == 'eval':

                    # evaluate key 
                    result = eval(key)
                    print "HMI:DEBUG: template retrieved EVAL value: {0}".format(result)

                    self.payload = self.payload.replace(origin, result)

                else:

                    print "HMI:DEBUG: could not substitute tag (source not implemented)"



class ThreadedHTTPServer(ThreadingMixIn, BaseHTTPServer.HTTPServer):
    """Handle requests in a separate thread."""

class SubHTTPServer(ThreadedHTTPServer):
    """this class is necessary to allow passing custom request handler into
       the RequestHandlerClass"""

    def __init__(self, server_address, RequestHandlerClass, template, docpath, snmp_host, snmp_port):
        BaseHTTPServer.HTTPServer.__init__(self, server_address, RequestHandlerClass)


        self.docpath = docpath
        self.snmp_host = snmp_host
        self.snmp_port = snmp_port
        

        # default configuration
        self.update_header_date = True              # this preserves authenticity
        self.disable_method_head = False            # considered to be safe
        self.disable_method_trace = True            # considered to be unsafe


        # load the configuration from template and parse it
        #  for the first time in order to reduce further handling..
        self.configuration = etree.parse(template)

        xml_config = self.configuration.xpath('//conpot_template/hmi/global/config/*')
        if xml_config:

            # retrieve all headers assigned to this status code
            for entity in xml_config:

                if entity.attrib['name'] == 'protocol_version':
                    #BaseHTTPServer.BaseHTTPRequestHandler.protocol_version = entity.text
                    RequestHandlerClass.protocol_version = entity.text
                    print "DEBUG: set proto version to "+entity.text

                elif entity.attrib['name'] == 'update_header_date':
                    if entity.text.lower() == 'false':
                        self.update_header_date = False
                        print "DEBUG: DATE header auto update disabled by configuration ( default: enabled )"
                    else:
                        self.update_header_date = True
                        print "DEBUG: DATE header auto update enabled by configuration ( default: enabled )"

                elif entity.attrib['name'] == 'disable_method_head':
                    if entity.text.lower() == 'true':
                        self.disable_method_head = True
                        print "DEBUG: HEAD method disabled by configuration ( default: enabled )"
                    else:
                        self.disable_method_head = False 
                        print "DEBUG: HEAD method enabled by configuration ( default: enabled )"

                elif entity.attrib['name'] == 'disable_method_trace':
                    if entity.text.lower() == 'false':
                        self.disable_method_trace = False
                        print "DEBUG: TRACE method enabled by configuration ( default: disabled )"
                    else:
                        self.disable_method_trace = True
                        print "DEBUG: TRACE method disabled by configuration ( default: disabled )"


        # load global headers from XML
        self.global_headers = []
        xml_headers = self.configuration.xpath('//conpot_template/hmi/global/headers/*')
        if xml_headers:

            # retrieve all headers assigned to this status code
            for header in xml_headers:
                print "checking header {0} and flag {1}".format(header.attrib['name'].lower(),self.update_header_date)
                if header.attrib['name'].lower() == 'date' and self.update_header_date == True:
                    self.global_headers.append((header.attrib['name'], self.date_time_string()))
                else:
                    self.global_headers.append((header.attrib['name'], header.text))


    def date_time_string(self, timestamp=None):
        """Return the current date and time formatted for a message header."""

        if timestamp is None:
            timestamp = time()
        year, month, day, hh, mm, ss, wd, y, z = gmtime(timestamp)
        s = "%s, %02d %3s %4d %02d:%02d:%02d GMT" % (
                self.weekdayname[wd],
                day, self.monthname[month], year,
                hh, mm, ss)
        return s


    weekdayname = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']

    monthname = [None,
                 'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
                 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']



class CommandResponder(object):

    def __init__(self, host, port, template, log_queue, docpath, snmp_host, snmp_port):

        self.log_queue = log_queue

        # Create HTTP server class
        self.httpd = SubHTTPServer((host, port), HTTPServer, template, docpath, snmp_host, snmp_port)

    def serve_forever(self):
        self.httpd.serve_forever()

    def stop(self):
        self.httpd.socket.close()



if __name__ == '__main__':
    http_server = HTTPServer()
    http_server.run()
