import socketserver
import gevent
from gevent import queue
import conpot.core as conpot_core
import logging
from gevent import socket
logger = logging.getLogger(__name__)

# -----------------------------------------------------------
# DTP channel that would have two queues for Input and Output. Separate producer and consumer.
# There would be 3 threads (greenlets) in place. One for handling the command_channel, one for handling the input/
# output of the data_channel and one that would copy uploads from from the data channel from the persistent file storage
#  - The FTP commands are kept in a separate class so that when we migrate to async-io only contents of the base class
# would require modifications. Commands class is independent of the **green drama**
# -----------------------------------------------------------
# Since FTP operations are usually I/O heavy, we would like to process the input from the client and the
# output concurrently yet separately. For this would use 2 green threads that could:
#   - read the socket, add any output to the _input_q
#   - write the socket, if we have any processed command/data available in the _output_q.
# Since we have 2 **dedicated full duplex channels** as per RFC-959 i.e. the command channel and the data channel,
# we need 2 x 2 = 4 green threads.
# -----------------------------------------------------------


class FTPHandlerBase(socketserver.BaseRequestHandler):
    """Base class for a full duplex connection"""
    config = None                # Config of FTP server.
    _data_listener_sock = None   # Listener socket for FTP active mode
    _data_sock = None            # Socket used for FTP data transfer
    _local_ip = '127.0.0.1'      # IP to bind the _data_listener_sock with.
    _ac_in_buffer_size = 65536   # incoming data buffer size (defaults 65536)
    _ac_out_buffer_size = 65536  # outgoing data buffer size (defaults 65536)

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
        self.working_dir = self.config.ftp_fs.getcwd()

        # flag to check whether we need to disconnect the client
        self.disconnect_client = False
        # keep state of the last command/response
        self._last_command = None
        self._last_response = None
        # stream, block or compressed
        self._transfer_mode = 'stream'
        # binary ('i') or ascii mode ('a')
        self._current_type = 'a'
        # buffer-size for FTP **commands**, send error if this is exceeded
        self.buffer_limit = 2048   # command channel would not accept more data than this for one command.

        self._active_passive_mode = None  # Flag to check the current mode. Would be set to 'PASV' or 'PORT'
        # FIXME: Make the above flag smarter? Use bool perhaps?
        self.cli_ip, self.cli_port = None, None     # IP and port received from client for active/passive mode.

        self.transfer_completed = False
        self.abort = False

        # Input and output queues.
        self._command_channel_input_q = gevent.queue.Queue()
        self._data_channel_input_q = gevent.queue.Queue()
        self._data_channel_output_q = gevent.queue.Queue()
        self.ftp_greenlets = None  # Keep track of all greenlets
        self.data_greenlets = None  # greenlets used for data channel.
        socketserver.BaseRequestHandler.__init__(self, request=request, client_address=client_address, server=server)

    # ------------------------ Wrappers for gevent StreamServer -------------------------

    class false_request(object):
        def __init__(self):
            self.sock = None

    @classmethod
    def stream_server_handle(cls, sock, address):
        """Translate this class for use in a StreamServer"""
        request = cls.false_request()
        server = None
        cls.srv_sock = sock
        try:
            cls(request, address, server)
            # TODO: Capture better exceptions.
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
        self.srv_sock.shutdown(socket.SHUT_RDWR)
        socketserver.BaseRequestHandler.finish(self)

    # ----------------------- FTP Command Processor --------------------

    def handle_command_channel(self, buffer_limit=None):
        """Read data from the socket and add it to the _command_channel_input_q for processing"""
        self.buffer_limit = buffer_limit if buffer_limit else self.buffer_limit
        # TODO: set the socket to non-blocking/set timeout
        # self.srv_sock.setblocking(False)
        log_data = dict()
        msg = self.srv_sock.recv(self.buffer_limit)
        log_data['request'] = msg
        logger.info('FTP traffic from {}: {} ({})', self.client_address[0], log_data, self.session.id)
        self.session.add_event(log_data)
        # Flush buffer if it gets too long (possible DOS condition). RFC-959 specifies that 500 response should be given
        # in such cases.
        if len(self._command_channel_input_q) > self.buffer_limit:
            logger.info('FTP command input exceeded buffer from client {}'.format(self.client_address))
            self.respond(b'500 Command too long.')
            # flush the contents
            msg = None
        if msg is not None:
            # put the data in the _input_q for processing
            self._command_channel_input_q.put(msg)

    def respond(self, response):
        """Send processed command/data as reply to the client"""
        log_data = dict()
        log_data['response'] = response
        response = response + self.terminator if response[-2:] != self.terminator else response
        if response is not None:
            try:
                logging.debug('Sending packet {} to client {}'.format(self.client_address, response))
                self.srv_sock.send(response)
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
        else:
            logger.info('Can\'t send NONE to client.')

    def process_ftp_command(self):
        """Must be implemented in child class"""
        raise NotImplementedError

    # ----------------------- FTP Data Channel --------------------

    def start_data_channel(self):
        """
        Starts the data channel in Active or Passive mode - as specified by the client. Binds relevant IPs, with ports.
        """
        # TODO: socket timeout!!
        if not self._active_passive_mode and self.data_greenlets is None:
            if self._active_passive_mode == 'PASV':
                # We are in passive mode. Here we would create a simple socket listener.
                self._data_listener_sock = socket.socket()
                # Note that we set the cli_ip and cli_port in the ftp_PASV command.

                if self._data_listener_sock:
                    try:
                        self._data_sock, (self.cli_ip, self.cli_port) = self._data_listener_sock.accept()
                        logger.info('Client {} entered FTP passive mode'.format(self.client_address))
                        logger.info('Client {} provided IP {} and Port for PASV connection.'.format(
                            self.client_address, self.cli_ip, self.cli_port)
                        )
                        while not (self.transfer_completed and self.abort):
                            self.data_greenlets = [gevent.spawn(self.data_channel_send_data),
                                                   gevent.spawn(self.data_channel_recv_data)]
                            # Block till all threads. But should terminate when the client is disconnected.
                            self.ftp_greenlets.append(self.data_greenlets)
                    except socket.error as se:
                        logger.info('Connection to client failed. Error occurred: {}'.format(str(se)))
                    finally:
                        self.stop_data_channel()
                else:
                    logger.info('Connection to client failed. Can\'t switch to PASV mode')
            else:
                # the client would tell us the port and client address to send the data to. We'll set that up in
                # ftp_PORT command.
                if self.cli_ip and self.cli_port:
                    self._data_sock = gevent.socket.socket()
                    try:
                        self._data_sock.connect((self.cli_ip, self.cli_port))
                        while not (self.transfer_completed and self.abort):
                            self.data_greenlets = [gevent.spawn(self.data_channel_send_data),
                                                   gevent.spawn(self.data_channel_recv_data)]
                            # Block till all threads. But should terminate when the client is disconnected.
                            self.ftp_greenlets.append(self.data_greenlets)
                    except socket.error as se:
                        logger.info('Can\'t switch to Active(PORT) mode. Error occurred: {}'.format(str(se)))
                    finally:
                        self.stop_data_channel()
                else:
                    logger.info('Can\'t initiate Active mode since either of IP or Port supplied by the client '
                                'are None')
        else:
            logger.info('Client in {} mode.'.format(self._active_passive_mode))

    def stop_data_channel(self):
        """
        Kills all data channel threads/sockets. Cleans and closes the buffers. Handles abort command.
        """
        if self.data_greenlets is not None:
            gevent.killall(self.data_greenlets)
            self.data_greenlets = None
        self._data_sock.close()
        self._active_passive_mode = None
        if self._active_passive_mode == 'PASV':
            self._data_listener_sock.close()
        # purge data in buffers .i.e the data queues.
        while self._data_channel_input_q.qsize() != 0:
            _ = self._data_channel_input_q.get()
        while self._data_channel_output_q.qsize() !=0:
            _ = self._data_channel_output_q.get()

    def data_channel_send_data(self):
        """
        Consumes data from the data channel output queue. Logs it and sends it across to the client.
        If a file needs to be send, pass the file name directly as file parameter.
        :param file: File that needs to sent across the data channel.
        """
        # pick an item from the _data_channel_output_q and send it to the requisite socket
        if not self._data_channel_output_q.empty() and self._data_sock:
            data = self._data_channel_output_q.get(block=self._ac_out_buffer_size)
            if isinstance(data, dict):
                if data['type'] == 'raw_data':
                    logger.info('Send data at {}:{} for client : {}'.format(self.cli_ip, self.cli_port,
                                                                            self.client_address))
                    self._data_sock.send(data=data)
                elif data['type'] == 'file':
                    file_name = data['file']
                    if self.config.ftp_fs.isfile(file_name):
                        logger.info('Sending file {} to client {} at {}:{}'.format(file_name, self.client_address,
                                                                                   self.cli_ip, self.cli_port))
                        self.respond(b'150 Initiating transfer.')
                        file_ = self.config.ftp_fs.open(file_name)
                        self._data_sock.sendfile(file=file_.fileno())
                        file_.close()
                        self.respond(b'226 Transfer complete.')

                else:
                    logger.info('Can\'t send. Unknown Type {} from data {}'.format(data['type'], data))
            else:
                logger.info('Invalid Type received: {}'.format(data))

    def data_channel_recv_data(self):
        """Receives data, logs it and add it to the data channel input queue."""
        data = self._data_sock.recv(self._ac_in_buffer_size)
        logger.debug('Received {} from client {} on {}:{}'.format(data, self.client_address, self.cli_ip, self.cli_port))
        self._data_channel_input_q.put(data)

    # ----------------------- FTP Authentication --------------------
    # FIXME: Refactor this.
    def authentication_ok(self, user_pass):
        """
            Verifies authentication and sets the username of the currently connected client. Returns True or False
                - Checks user names and passwords pairs. Sets the current user
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

    # ----------------------- Actual FTP Handler --------------------

    def handle(self):
        """Actual FTP service to which the user has connected."""
        while not self.disconnect_client:
            try:
                # These greenlets would be running forever. During the connection.
                # first two are for duplex command channel. Latter two are for storing files on file-systems.
                self.ftp_greenlets = [gevent.spawn(self.process_ftp_command),
                                      gevent.spawn(self.handle_command_channel)]
                gevent.joinall(self.ftp_greenlets)
                # Block till all jobs are not finished
            finally:
                gevent.killall(self.ftp_greenlets)