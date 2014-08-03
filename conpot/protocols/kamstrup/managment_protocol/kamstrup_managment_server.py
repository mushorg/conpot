
import logging
import socket

from gevent.server import StreamServer

import conpot.core as conpot_core

logger = logging.getLogger(__name__)


class KamstrupManagmentServer(object):
    def __init__(self, template, timeout=0):
        self.template = template
        self.timeout = timeout

        logger.info('Kamstrup managment protocol server initialized.')

    def handle(self, sock, address):
        session = conpot_core.get_session('kamstrup_managment_protocol', address[0], address[1])
        logger.info('New connection from {0}:{1}. ({2})'.format(address[0], address[1], session.id))

        try:
            while True:
                # incomming request
                raw_request = sock.recv(1024)

                if not raw_request:
                    logger.info('Client disconnected. ({0})'.format(session.id))
                    break

                logdata = {'request': raw_request}
                # for many of the other protocols we used a seperate command responder
                # to create a proper response to requests... You might also want to do this.
                #response = self.command_responder.respond(request)
                response = "dummy response"
                logdata['response'] = response
                logger.debug('Kamstrup managment traffic from {0}: {1} ({2})'.format(address[0], logdata, session.id))
                session.add_event(logdata)
                sock.send(response)
        except socket.timeout:
            logger.debug('Socket timeout, remote: {0}. ({1})'.format(address[0], session.id))

        sock.close()

    def get_server(self, host, port):
        connection = (host, port)
        server = StreamServer(connection, self.handle)
        logger.info('Kamstrup managment protocol server started on: {0}'.format(connection))
        return server


