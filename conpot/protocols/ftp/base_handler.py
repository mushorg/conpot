from gevent import monkey; monkey.patch_all()
import socketserver
import gevent
from gevent import queue
from gevent import select
import conpot.core as conpot_core
from conpot.core.file_io import FilesystemError
import logging
import errno
import fs
import glob
from fs import errors
from gevent import event
import sys
from conpot.protocols.ftp.ftp_utils import FTPPrivilegeException
from datetime import datetime
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


class FTPMetrics(object):
    """Simple class to track total bytes transferred, login attempts etc."""
    def __int__(self):
        self.start_time = datetime.now()
        self.end_time = None

    def get_command_channel_metrics(self):
        pass

    def get_data_channel_metrics(self):
        pass

    def get_elasped_time(self):
        pass


# The requirements of the data_channel and the command_channel are as follows:
# -


class FTPHandlerBase(socketserver.BaseRequestHandler):
    """Base class for a full duplex connection"""
    config = None                # Config of FTP server. FTPConfig class instance.
    _local_ip = '127.0.0.1'      # IP to bind the _data_listener_sock with.
    _ac_in_buffer_size = 4096    # incoming data buffer size (defaults 65536)
    _ac_out_buffer_size = 4096   # outgoing data buffer size (defaults 65536)

    def __init__(self, request, client_address, server):

        # ------------------------ Environment -------------------------
        self.client_sock = request._sock
        # only commands that are enabled should work! This is configured in the FTPConfig class.
        if not self._local_ip:
            self._local_ip = self.client_sock.getsockname()[0]  # for masquerading.. Local IP would work just fine.
        # Username of the current user
        self.username = None
        self._uid = None  # UID of the current username
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
        self.root = self.config.vfs.norm_path(self.config.vfs.getcwd() + '/')
        self.working_dir = '/'
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
        self.active_passive_mode = None  # Flag to check the current mode. Would be set to 'PASV' or 'PORT'

        self._data_channel = gevent.event.Event()  # check whether the data channel is running or not. This would trigger
        # the start and end of the data channel.
        self.cli_ip, self.cli_port = None, None     # IP and port received from client for active/passive mode.
        self._data_sock = None
        self._data_listener_sock = None
        # socket for accepting cli_ip and cli_port in passive mode.

        self.abort = False
        self.transfer_complete = False
        self._rnfr = None  # For RNFR and RNTO

        # Input and output queues.
        self._command_channel_input_q = gevent.queue.Queue()
        self._command_channel_output_q = gevent.queue.Queue()
        self._data_channel_output_q = gevent.queue.Queue()
        self._data_channel_input_q = gevent.queue.Queue()
        self.ftp_greenlets = None  # Keep track of all greenlets
        socketserver.BaseRequestHandler.__init__(self, request=request, client_address=client_address,
                                                 server=server)

    # ------------------------ Wrappers for gevent StreamServer -------------------------

    class false_request(object):
        def __init__(self):
            self._sock = None

        def __del__(self):
            if self._sock:
                if self._sock.fileno() != -1:
                    self._sock.close()
                del self._sock

    @classmethod
    def stream_server_handle(cls, sock, address):
        """Translate this class for use in a StreamServer"""
        request = cls.false_request()
        request._sock = sock
        server = None
        _ftp = None
        try:
            _ftp = cls(request, address, server)
        except socket.error:
            logger.warning('Unexpected Error Occurred!')
            del _ftp

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
        logger.info('FTP client {} disconnected. ({})'.format(self.client_address, self.session.id))
        self.stop_data_channel(abort=True, purge=True, reason='Closing connection to {}. Client disconnected'.format(
            self.client_address
        ))
        if self._data_listener_sock:
            if self._data_listener_sock.fileno() != -1:
                self._data_sock.close()
        self.client_sock.close()
        socketserver.BaseRequestHandler.finish(self)

    def __del__(self):
        self.finish()
        
    # ------------------------ FTP Command Channel -------------------------

    def handle_cmd_channel(self):
        """Read data from the socket and add it to the _command_channel_input_q for processing"""
        log_data = dict()
        try:
            socket_read, socket_write, _ = gevent.select.select([self.client_sock], [self.client_sock], [], 1)
            # make sure the socket is ready to read - we would read from the command channel.
            if self.client_sock in socket_read:
                data = self.client_sock.recv(self.buffer_limit)
                # put the data in the _input_q for processing
                if data and data != b'':
                    log_data['request'] = data
                    logger.info('FTP traffic to {}: {} ({})'.format(self.client_address, log_data,
                                                                    self.session.id))
                    self.session.add_event(log_data)
                    if self._command_channel_input_q.qsize() > self.buffer_limit:
                        # Flush buffer if it gets too long (possible DOS condition). RFC-959 specifies that
                        # 500 response should be given in such cases.
                        logger.info('FTP command input exceeded buffer from client {}'.format(
                            self.client_address)
                        )
                        self.respond(b'500 Command too long.')
                    else:
                        self._command_channel_input_q.put(data)
            # make sure the socket is ready to write
            elif self.client_sock in socket_write and (not self._command_channel_output_q.empty()):
                response = self._command_channel_output_q.get()
                if response is not None:
                    log_data = dict()
                    logger.debug('Sending packet {} to client {}'.format(self.client_address, response))
                    log_data['response'] = response
                    self.client_sock.send(response)
                    logger.info('FTP traffic to {}: {} ({})'.format(self.client_address, log_data, self.session.id))
                    self.session.add_event(log_data)
            else:
                gevent.sleep(0)
        except socket.timeout:
            logger.info('Socket timeout, remote: {}. ({})'.format(self.client_address, self.session.id))
            self.session.add_event({'type': 'CONNECTION_TIMEOUT'})
            self.finish()
        except socket.error as se:
            if se.errno == errno.EWOULDBLOCK:
                gevent.sleep(0.1)
            else:
                logger.info('Socket error, remote: {}. ({}). Error {}'.format(self.client_address, self.session.id, se))
                self.session.add_event({'type': 'CONNECTION_LOST'})
                self.finish()
    
    def respond(self, response):
        """Send processed command/data as reply to the client"""
        response = response.encode('utf-8') if not isinstance(response, bytes) else response
        response = response + self.terminator if response[-2:] != self.terminator else response
        self._command_channel_output_q.put(response)

    # Helper methods and Command Processors.
    def _log_err(self, err):
        """
        Log errors and send an unexpected response standard message to the client.
        :param err: Exception object
        :return: 500 msg to be sent to the client.
        """
        logger.info('FTP error occurred. Client: {} error {}'.format(self.client_address, str(err)))

    # clean things, sanity checks and more
    def _pre_process_cmd(self, line, cmd, arg):
        kwargs = {}
        if cmd == "SITE" and arg:
            cmd = "SITE %s" % arg.split(' ')[0].upper()
            arg = line[len(cmd) + 1:]

        logger.info('Received command {} : {} from FTP client {}: {}'.format(cmd, line, self.client_address,
                                                                             self.session.id))
        if cmd not in self.config.COMMANDS:
            if cmd[-4:] in ('ABOR', 'STAT', 'QUIT'):
                cmd = cmd[-4:]
            else:
                self.respond(b'500 Command %a not understood' % cmd)
                return

        # - checking for valid arguments
        if not arg and self.config.COMMANDS[cmd]['arg'] is True:
            self.respond(b"501 Syntax error: command needs an argument")
            return
        if arg and self.config.COMMANDS[cmd]['arg'] is False:
            self.respond(b'501 Syntax error: command does not accept arguments.')
            return

        if not self.authenticated:
            if self.config.COMMANDS[cmd]['auth'] or (cmd == 'STAT' and arg):
                self.respond(b'530 Log in with USER and PASS first.')
                return
            else:
                # call the proper do_* method
                self._process_command(cmd, arg)
                return
        else:
            # if (cmd == 'STAT') and not arg:
            #     self.do_STAT()
            #     return

            # for file-system related commands check whether real path
            # destination is valid
            if self.config.COMMANDS[cmd]['perm'] and (cmd != 'STOU'):
                if cmd in ('CWD', 'XCWD'):
                    if arg and self.working_dir != '/':
                        arg = '/'.join([self.config.vfs.norm_path(self.working_dir), arg])
                    else:
                        arg = self.config.vfs.norm_path(arg or '/')
                elif cmd in ('CDUP', 'XCUP'):
                    arg = ''
                elif cmd == 'LIST':
                    if arg.lower() in ('-a', '-l', '-al', '-la'):
                        arg = self.config.vfs.norm_path(self.working_dir)
                    else:
                        arg = self.config.vfs.norm_path(arg or self.working_dir)
                    return
                elif cmd == 'STAT':
                    if glob.has_magic(arg):
                        self.respond(b'550 Globbing not supported.')
                        return
                    arg = self.config.vfs.norm_path(arg or self.working_dir)
                elif cmd == 'SITE CHMOD':
                    if ' ' not in arg:
                        self.respond(b'501 Syntax error: command needs two arguments.')
                        return
                    else:
                        mode, arg = arg.split(' ', 1)
                        arg = self.config.vfs.norm_path(arg)
                        kwargs = dict(mode=mode)
                else:
                    if glob.has_magic(arg):
                        self.respond(b'550 Globbing not supported.')
                        return
                    else:
                        arg = glob.escape(arg)
                        arg = self.config.vfs.norm_path(arg or self.working_dir)
                        arg = line.split(' ', 1)[1] if arg is None else arg

            # call the proper do_* method
            self._process_command(cmd, arg, **kwargs)

    def _process_command(self, cmd, *args, **kwargs):
        """Process command by calling the corresponding do_* class method (e.g. for received command "MKD pathname",
        do_MKD() method is called with "pathname" as the argument).
        """
        if self.invalid_login_attempt > self.max_login_attempts:
            self.respond(b'550 Permission denied. (Exceeded maximum permitted login attempts)')
            self.disconnect_client = True
        else:
            try:
                method = getattr(self, 'do_' + cmd.replace(' ', '_'))
                self._last_command = cmd
                method(*args, **kwargs)
                if self._last_response:
                    code = int(self._last_response[:3])
                    resp = self._last_response[4:]
                    logger.debug('Last response {}:{} Client {}:{}'.format(code, resp, self.client_address,
                                                                           self.session.id))
            except (fs.errors.FSError, FilesystemError):
                raise

    # - main command processor
    def process_ftp_command(self):
        """
        Handle an incoming handle request - pick and item from the input_q, reads the contents of the message and
        dispatch contents to the appropriate do_* method.
        :param: (bytes) line - incoming request
        :return: (bytes) response - reply in respect to the request
        """
        try:
            if not self._command_channel_input_q.empty():
                # decoding should be done using utf-8
                line = self._command_channel_input_q.get().decode()
                # Remove any CR+LF if present
                line = line[:-2] if line[-2:] == '\r\n' else line
                if line:
                    cmd = line.split(' ')[0].upper()
                    arg = line[len(cmd) + 1:]
                    try:
                        self._pre_process_cmd(line, cmd, arg)
                    except UnicodeEncodeError:
                        self.respond(b'501 can\'t decode path (server filesystem encoding is %a)' %
                                     sys.getfilesystemencoding())
                    except fs.errors.PermissionDenied:
                        # TODO: log user as well.
                        logger.info('Client {} requested path: {} trying to access directory to which it has '
                                    'no access to.'.format(self.client_address, line))
                        self.respond(b'500 Permission denied')
                    except fs.errors.IllegalBackReference:
                        # Trying to access the directory which the current user has no access to
                        self.respond(b'550 %a points to a path which is outside the user\'s root directory.' %
                                     line)
                    except FTPPrivilegeException:
                        self.respond(b'550 Not enough privileges.')
                    except (fs.errors.FSError, FilesystemError) as fe:
                        logger.info('FTP client {} Unexpected error occurred : {}'.format(self.client_address, fe))
                        # TODO: what to respond here? For now just terminate the session
                        self.disconnect_client = True
            else:
                gevent.sleep(0)

        except UnicodeDecodeError:
            # RFC-2640 doesn't mention what to do in this case. So we'll just return 501
            self.respond(b"501 can't decode command.")

    # ----------------------- FTP Data Channel --------------------

    def start_data_channel(self):
        if not self._data_channel.ready():
            self._data_channel.set()

    def stop_data_channel(self, abort=False, purge=False, reason=None):
        if reason:
            logger.info('Closing data channel. Reason: {}'.format(reason))
        if (not self._data_channel_output_q.empty()) or (not self._command_channel_input_q.empty()):
            if not abort:
                # Wait for all transfers to complete.
                self._data_channel.wait()
            else:
                self._data_channel.clear()
        if purge:
            self.cli_ip = None
            self.cli_port = None
            # purge data in buffers .i.e the data queues.
            while self._data_channel_input_q.qsize() != 0:
                _ = self._data_channel_input_q.get()
            while self._data_channel_output_q.qsize() != 0:
                _ = self._data_channel_output_q.get()
            if self._data_sock and self._data_sock.fileno() != -1:
                self._data_sock.close()

    def handle_data_channel(self):
        if self._data_channel.ready():
            try:
                assert self.cli_ip and self.cli_port
                socket_read, socket_write, socket_err = gevent.select.select([self._data_sock], [self._data_sock],
                                                                             [self._data_sock], 1)
                if len(socket_err) > 0 or (self.transfer_complete or self.abort or self.disconnect_client):
                    self.stop_data_channel(abort=True, purge=True, reason='Exception occurred.')
                else:
                    if self._data_sock in socket_read:
                        self.data_channel_recv_data()
                    elif self._data_sock in socket_write:
                        self.data_channel_send_data()
            except AssertionError:
                self.respond(b'425 Use PORT or PASV first.')
                self.stop_data_channel(reason='Can\'t initiate {} mode since either of IP or Port supplied by the '
                                              'client are None'.format(self.active_passive_mode))
            except socket.timeout:
                # Flush contents of the data channel
                # TODO: send appropriate response
                self.stop_data_channel(abort=True, purge=True,
                                       reason='FTP data channel {} : connection timed out for '
                                              '({}:{}).'.format(self.client_address, self.cli_ip, self.cli_port))
            except socket.error:
                # There was a socket error while data transfer. Request cli_ip and cli_port again. Also flush contents
                # of the data channel
                # TODO: send appropriate response
                self.stop_data_channel(abort=True, purge=True,
                                       reason='FTP data channel {} : socket error occurred for '
                                              '({}:{}).'.format(self.client_address, self.cli_ip, self.cli_port))
            except (fs.errors.FSError, FilesystemError, FTPPrivilegeException, FilesystemError) as fe:
                self.stop_data_channel(abort=True, reason='VFS related exception occurred: {}'.format(str(fe)))
        else:
            gevent.sleep(0)

    def data_channel_send_data(self):
        """
        Consumes data from the data channel output queue. Logs it and sends it across to the client.
        If a file needs to be send, pass the file name directly as file parameter.
        """
        # pick an item from the _data_channel_output_q and send it to the requisite socket
        if not self._data_channel_output_q.empty():
            data = self._data_channel_output_q.get(block=self._ac_out_buffer_size)
            if isinstance(data, dict):
                if data['type'] == 'raw_data':
                    logger.info('Send data {} at {}:{} for client : {}'.format(data['data'], self.cli_ip,
                                                                               self.cli_port,
                                                                               self.client_address))
                    self._data_sock.send(data=data['data'])
                elif data['type'] == 'file':
                    file_name = data['file']
                    if self.config.vfs.isfile(file_name):
                        logger.info('Sending file {} to client {} at {}:{}'.format(file_name,
                                                                                   self.client_address,
                                                                                   self.cli_ip,
                                                                                   self.cli_port))
                        self.respond(b'150 Initiating transfer.')
                        file_ = self.config.vfs.open(file_name, mode='r')
                        self._data_sock.sendfile(file=file_.fileno())
                        file_.close()
                        self.respond(b'226 Transfer complete.')
                else:
                    logger.info('Can\'t send. Unknown Type {} from data {}'.format(data['type'], data))
            else:
                logger.debug('Invalid Type received: {}'.format(data))
        else:
            logger.debug('No data to write. Transfer Complete! Closing data channel.')
            self._data_channel.clear()

    def data_channel_recv_data(self):
        """Receives data, logs it and add it to the data channel input queue."""
        data = self._data_sock.recv(self._ac_in_buffer_size)
        logger.debug('Received {} from client {} on {}:{}'.format(data, self.client_address, self.cli_ip,
                                                                  self.cli_port))
        self._data_channel_input_q.put(data)

    def push_data(self, data):
        """Handy utility to push some data using the data channel"""
        # ensure data is encoded in bytes
        data = data.encode('utf8') if not isinstance(data, bytes) else data
        if self._data_channel.is_set():
            self.respond("125 Data connection already open. Transfer starting.")
            self._data_channel_output_q.put({'type': 'raw_data', 'data': data})
        else:
            self.respond("150 File status okay. About to open data connection.")

    def send_file(self, file_name):
        """Handy utility to send a file using the data channel"""
        self._data_channel_output_q.put({'type': 'file', 'file': file_name})

    # ----------------------- FTP Authentication and other unities --------------------

    # FIXME: Refactor this. Move this to the auth module.
    def authentication_ok(self, user_pass):
        """
            Verifies authentication and sets the username of the currently connected client. Returns True or False
                - Checks user names and passwords pairs. Sets the current user
                - Getting/Setting user home directory
                - Checking user permissions when a filesystem read/write event occurs
                - Creates VFS instances *per* user/pass tuple. Also stores the state of the user (cwd, permissions etc.)
            If it is not the first time a user has logged in, it would fetch the vfs from existing vfs instances.
        """
        # if anonymous ftp is enabled - accept any password.
        try:
            if self.username == 'anonymous' and self.config.anon_auth:
                self.authenticated = True
                return True
            else:
                if (self.username, user_pass) in self.config.user_pass:
                    # user/pass match and correct!
                    self.authenticated = True
                    [self._uid] = [k for k, v in self.config.user_db.items() if self.username in v.values()]
                    return True
                return False
        except (KeyError, ValueError):
            return False

    def check_perms(self, perms='r', path=None):
        # check permission
        if path is None:
            _path = self.working_dir
        else:
            _path = path
        if self.config.has_permissions(file_path=_path, uid=self._uid, perms=perms):
            return True
        else:
            raise FTPPrivilegeException
        
    # ----------------------- Actual FTP Handler --------------------

    def handle(self):
        """Actual FTP service to which the user has connected."""
        while not self.disconnect_client:
            try:
                # These greenlets would be running forever. During the connection.
                # first two are for duplex command channel. Latter two are for storing files on file-systems.
                self.ftp_greenlets = [gevent.spawn(self.handle_cmd_channel),
                                      gevent.spawn(self.process_ftp_command),
                                      gevent.spawn(self.handle_data_channel)]
                gevent.joinall(self.ftp_greenlets)
                # Block till all jobs are not finished
            finally:
                gevent.killall(self.ftp_greenlets)