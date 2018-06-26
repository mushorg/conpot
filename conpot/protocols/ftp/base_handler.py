import socketserver
import gevent
from gevent import queue
import conpot.core as conpot_core
import logging
from gevent import socket
logger = logging.getLogger(__name__)


class FTPHandlerBase(socketserver.BaseRequestHandler):
    """Base class for a full duplex connection"""
    config = None
    client_sock = None

    def __init__(self, request, client_address, server):

        # ------------------------ Environment -------------------------
        # Username of the current user
        self.username = None
        # The flag to check whether a user is already authenticated!
        self.authenticated = False

        # What commands does this FTP support
        self.COMMANDS = {}
        # conpot session
        self.session = None
        # terminate character - CR+LF
        self.terminator = b'\r\n'
        # tracking login attempts
        self.invalid_login_attempt = 0
        # max login attempts
        self.max_login_attempts = 3

        # get the current working directory of the current user
        self.working_dir = None

        # flag to check whether we need to disconnect the client
        self.disconnect_client = False
        # keep state of the last command/response
        self._last_command = None
        self._last_response = None
        # stream, block or compressed
        self._mode = None
        # binary ('i') or ascii mode ('a')
        self._current_type = 'a'
        # buffer-size for FTP commands, send error if this is exceeded
        self.buffer_limit = 2048

        # Since FTP operations are usually I/O heavy, we would like to process the input from the client and the
        # output concurrently yet separately. For this would use 2 green threads that could :
        #   - read the socket, add any output to the _input_q
        #   - write the socket, if we have any processed command/data available in the _output_q.
        self._input_q = gevent.queue.Queue()
        self.ftp_greenlets = None
        socketserver.BaseRequestHandler.__init__(self, request=request, client_address=client_address, server=server)

    # ------------------------ Wrappers for gevent StreamServer etc. -------------------------

    class false_request(object):
        def __init__(self):
            self.sock = None

    @classmethod
    def stream_server_handle(cls, sock, address):
        """Translate this class for use in a StreamServer"""
        request = cls.false_request()
        request._sock = sock
        server = None
        cls.client_sock = sock
        try:
            cls(request, address, server)
        except Exception:
            logging.exception('Unexpected Error Occurred!')

    def setup(self):
        """Connect incoming connection to a FTP session"""
        self.session = conpot_core.get_session('ftp', self.client_address[0], self.client_address[1])
        logger.info('New FTP connection from {}:{}. ({})'.format(self.client_address[0], self.client_address[1],
                                                                 self.session.id))
        self.session.add_event({'type': 'NEW_CONNECTION'})
        # send 200 + banner -- new client has connected!
        # TODO: accommodate motd
        self.respond(b'200 ' + self.config.banner.encode())
        #  Is there a delay in command response? < gevent.sleep(0.5) ?
        return socketserver.BaseRequestHandler.setup(self)

    def finish(self):
        """End this client session"""
        logger.info('FTP client {} disconnected. ({})', self.client_address, self.session.id)
        self.client_sock.shutdown(socket.SHUT_RDWR)
        socketserver.BaseRequestHandler.finish(self)

    # ----------------------- FTP Command Processor --------------------

    def recv_data(self, buffer_limit=None):
        """Read data from the socket and add it to the _input_q for processing"""
        self.buffer_limit = buffer_limit if buffer_limit else self.buffer_limit
        # TODO: set the socket to non-blocking/set timeout
        # self.client_sock.setblocking(False)
        log_data = dict()
        msg = self.client_sock.recv(self.buffer_limit)
        log_data['request'] = msg
        logger.info('FTP traffic from {}: {} ({})', self.client_address[0], log_data, self.session.id)
        self.session.add_event(log_data)
        # Flush buffer if it gets too long (possible DOS condition). RFC-959 specifies that 500 response should be given
        # in such cases.
        if len(self._input_q) > self.buffer_limit:
            logger.info('FTP command input exceeded buffer from client {}'.format(self.client_address))
            self.respond(b'500 Command too long.')
            # flush the contents
            msg = None
        if msg is not None:
            # put the data in the _input_q for processing
            self._input_q.put(msg)

    def respond(self, response):
        """Send processed command/data as reply to the client"""
        log_data = dict()
        log_data['response'] = response
        response = response + self.terminator if response[-2:] != self.terminator else response
        if response is not None:
            try:
                logging.debug('Sending packet {} to client {}'.format(self.client_address, response))
                self.client_sock.send(response)
                logger.info('FTP traffic to {}: {} ({})', self.client_address[0], log_data, self.session.id)
                self.session.add_event(log_data)
            except socket.timeout:
                logger.debug('Socket timeout, remote: {}. ({})', self.client_address[0], self.session.id)
                self.session.add_event({'type': 'CONNECTION_TIMEOUT'})
                self.finish()
            except socket.error:
                logger.debug('Socket error, remote: {}. ({})', self.client_address[0], self.session.id)
                self.session.add_event({'type': 'CONNECTION_LOST'})
                self.finish()

    def process_ftp_command(self):
        """Must be implemented in child class"""
        raise NotImplementedError

    def handle(self):
        """Actual FTP service to which the user has connected."""
        while not self.disconnect_client:
            try:
                self.ftp_greenlets = [gevent.spawn(self.process_ftp_command), gevent.spawn(self.recv_data)]
                gevent.joinall(self.ftp_greenlets)
                # Block till all jobs are not finished
            finally:
                gevent.killall(self.ftp_greenlets)

    # ----------------------- FTP Authentication --------------------
    # FIXME: Refactor this.
    def authentication_ok(self, user_pass):
        """
            Verifies authentication and sets the username of the currently connected client. Returns True or False
                - Checks usernames and passwords pairs. Sets the current user
                - Getting/Setting user home directory
                - Checking user permissions when a filesystem read/write event occurs
                - Creates VFS instances *per* user/pass tuple. Also stores the state of the user (cwd, permissions etc.)
            If it is not the first time a user has logged in, it would fetch the vfs from existing vfs instances.
        """
        # if anonymous ftp is enabled
        if self.username == 'anonymous' and user_pass == '' and self.config.anon_auth:
            # create anonymous db - vfs
            # TODO: should change with the vfs. Fow now, let us keep this
            # self.config.ftp_fs = os
            self.authenticated = True
            return True
        else:
            if user_pass and self.username:
                if self.username in self.config.user_db.keys():
                    if self.config.user_db[self.username] == user_pass:
                        # user/pass match and correct!
                        # TODO: If there already exists an instance of FTP for this current user, return that vfs
                        # else create a new vfs for this user.
                        # self.config.ftp_fs = os
                        self.authenticated = True
                        return True
                    return False