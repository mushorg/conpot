import fs
import os
import logging
import tftpy
import time
from gevent import socket
from tftpy import TftpException, TftpErrors
from tftpy.TftpStates import TftpStateExpectACK, TftpStateExpectDAT
from tftpy.TftpPacketTypes import TftpPacketRRQ, TftpPacketWRQ
from conpot.helpers import sanitize_file_name

logger = logging.getLogger(__name__)


class TFTPState(tftpy.TftpStates.TftpState):
    def __int__(self, context):
        super().__init__(context)

    def handle(self, pkt, raddress, rport):
        raise NotImplementedError


class TFTPServerState(TFTPState):
    """The base class for server states. """

    # We had to rewrite the because -- had to check os.* wrappers.
    vfs, data_fs = None, None
    full_path = None

    def handle(self, pkt, raddress, rport):
        raise NotImplementedError

    def serverInitial(self, pkt, raddress, rport):
        options = pkt.options
        sendoack = False
        if not self.context.tidport:
            self.context.tidport = rport
            logger.info("Setting tidport to %s" % rport)

        logger.debug("Setting default options, blksize")
        self.context.options = {"blksize": tftpy.DEF_BLKSIZE}

        if options:
            logger.debug("Options requested: %s", options)
            supported_options = self.returnSupportedOptions(options)
            self.context.options.update(supported_options)
            sendoack = True
        # FIXME - only octet mode is supported at this time.
        if pkt.mode != "octet":
            logger.info("Received non-octet mode request. Replying with binary data.")

        # test host/port of client end
        if self.context.host != raddress or self.context.port != rport:
            self.sendError(TftpErrors.UnknownTID)
            logger.error(
                "Expected traffic from %s:%s but received it from %s:%s instead."
                % (self.context.host, self.context.port, raddress, rport)
            )
            # Return same state, we're still waiting for valid traffic.
            return self
        logger.debug("Requested filename is %s", pkt.filename)
        if pkt.filename.startswith(self.context.root):
            full_path = pkt.filename
        else:
            full_path = os.path.join(self.context.root, pkt.filename.lstrip("/"))
        try:
            logger.info("Full path of file to be uploaded is {}".format(full_path))
            self.full_path = full_path
        except fs.errors.FSError:
            logger.warning("requested file is not within the server root - bad")
            self.sendError(TftpErrors.IllegalTftpOp)
            raise TftpException("Bad file path")
        self.context.file_to_transfer = pkt.filename
        return sendoack


class TFTPStateServerRecvRRQ(TFTPServerState):
    def handle(self, pkt, raddress, rport):
        """Handle an initial RRQ packet as a server."""
        logger.debug("In TftpStateServerRecvRRQ.handle")
        sendoack = self.serverInitial(pkt, raddress, rport)
        path = self.full_path
        logger.info("Opening file %s for reading" % path)
        if self.context.vfs.norm_path(path):
            self.context.fileobj = self.context.vfs.open(
                path.replace(self.context.root + "/", ""), "rb"
            )
        else:
            logger.info("File not found: %s", path.replace(self.context.root + "/", ""))
            self.sendError(TftpErrors.FileNotFound)
            raise TftpException("File not found: {}".format(path))

        # Options negotiation.
        if sendoack and "tsize" in self.context.options:
            # getting the file size for the tsize option. As we handle
            # file-like objects and not only real files, we use this seeking
            # method instead of asking the OS
            self.context.fileobj.seek(0, os.SEEK_END)
            tsize = str(self.context.fileobj.tell())
            self.context.fileobj.seek(0, 0)
            self.context.options["tsize"] = tsize

        if sendoack:
            # Note, next_block is 0 here since that's the proper
            # acknowledgement to an OACK.
            # FIXME: perhaps we do need a TftpStateExpectOACK class...
            self.sendOACK()
            # Note, self.context.next_block is already 0.
        else:
            self.context.next_block = 1
            logger.debug("No requested options, starting send...")
            self.context.pending_complete = self.sendDAT()
        # Note, we expect an ack regardless of whether we sent a DAT or an
        # OACK.
        return TftpStateExpectACK(self.context)

        # Note, we don't have to check any other states in this method, that's
        # up to the caller.


class TFTPStateServerRecvWRQ(TFTPServerState):
    """This class represents the state of the TFTP server when it has just
    received a WRQ packet."""

    def make_subdirs(self):
        """The purpose of this method is to, if necessary, create all of the
        subdirectories leading up to the file to the written."""
        # Pull off everything below the root.
        subpath = self.full_path[len(self.context.root) :]
        subpath = subpath.decode() if isinstance(subpath, bytes) else subpath
        logger.debug("make_subdirs: subpath is %s", subpath)
        # Split on directory separators, but drop the last one, as it should
        # be the filename.
        dirs = subpath.split("/")[:-1]
        logger.debug("dirs is %s", dirs)
        current = self.context.root
        for dir in dirs:
            if dir:
                current = os.path.join(current, dir)
                if self.context.vfs.isdir(current):
                    logger.debug("%s is already an existing directory", current)
                else:
                    self.context.vfs.makedir(current, 0o700)

    def handle(self, pkt, raddress, rport):
        """Handle an initial WRQ packet as a server."""
        logger.debug("In TFTPStateServerRecvWRQ.handle")
        sendoack = self.serverInitial(pkt, raddress, rport)
        path = self.full_path
        self.context.file_path = path
        path = path.decode() if isinstance(path, bytes) else path
        logger.info("Opening file %s for writing" % path)
        if self.context.vfs.exists(path):
            logger.warning(
                "File %s exists already, overwriting..."
                % (self.context.file_to_transfer)
            )
        self.make_subdirs()
        self.context.fileobj = self.context.vfs.open(path, "wb")
        # Options negotiation.
        if sendoack:
            logger.debug("Sending OACK to client")
            self.sendOACK()
        else:
            logger.debug("No requested options, expecting transfer to begin...")
            self.sendACK()
        self.context.next_block = 1
        return TftpStateExpectDAT(self.context)


class TFTPStateServerStart(TFTPState):
    """The start state for the server. This is a transitory state since at
    this point we don't know if we're handling an upload or a download. We
    will commit to one of them once we interpret the initial packet."""

    def handle(self, pkt, raddress, rport):
        """Handle a packet we just received."""
        logger.debug("Using TFTPStateServerStart.handle")
        if isinstance(pkt, TftpPacketRRQ):
            logger.debug("Handling an RRQ packet")
            return TFTPStateServerRecvRRQ(self.context).handle(pkt, raddress, rport)
        elif isinstance(pkt, TftpPacketWRQ):
            logger.debug("Handling a WRQ packet")
            return TFTPStateServerRecvWRQ(self.context).handle(pkt, raddress, rport)
        else:
            self.sendError(tftpy.TftpErrors.IllegalTftpOp)
            raise TftpException("Invalid packet to begin upload/download: %s" % pkt)


class TFTPContextServer(tftpy.TftpContexts.TftpContextServer):
    """Simple TFTP server handler wrapper. Use conpot's filesystem wrappers rather than os.*"""

    file_path = None
    _already_uploaded = (
        False  # Since with UDP, we can't differentiate between when a user disconnected
    )
    # after successful upload and when the client timed out, we would allow file copy on data_fs only once

    def __int__(self, host, port, timeout, root, dyn_file_func, upload_open):
        tftpy.TftpContexts.TftpContextServer.__init__(
            self,
            host=host,
            port=port,
            timeout=timeout,
            root=root,
            dyn_file_func=None,
            upload_open=None,
        )
        self.state = TFTPStateServerStart(self)
        self.log = logger
        self.state.log = logger
        self.root = root
        if self.sock:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.sock.bind("", 0)
        self.data_fs_fileobj = None
        self.vfs = None
        self.data_fs = None
        self.sock.setblocking(False)

    def start(self, buffer):
        logger.debug(
            "In TFTPContextServer - Starting TFTP context with : {}".format(buffer)
        )
        self.metrics.start_time = time.time()
        self.last_update = time.time()
        pkt = self.factory.parse(buffer)
        self.state = TFTPStateServerStart(self)
        self.state = self.state.handle(pkt, self.host, self.port)

    def end(self):
        logger.debug("In TFTPContextServer.end - closing socket and files.")
        self.sock.close()
        if self.fileobj is not None and not self.fileobj.closed:
            logger.debug("self.fileobj is open - closing")
            self.fileobj.close()
        if not self.state and (not self._already_uploaded):
            if self.file_path:
                # Return None only when transfer is complete!
                logger.info("TFTP : Transfer Complete!")
                _file_path = (
                    self.file_path
                    if isinstance(self.file_path, str)
                    else self.file_path.decode()
                )
                _data_fs_filename = sanitize_file_name(
                    "".join(_file_path.split("/")[-1:]), self.host, self.port
                )
                logger.info("Opening {} for data_fs writing.".format(_data_fs_filename))
                with self.vfs.open(_file_path, "rb") as _vfs_file:
                    with self.data_fs.open(_data_fs_filename, "wb") as _data_file:
                        content = _vfs_file.read()
                        _data_file.write(content)
            self._already_uploaded = True
        self.metrics.end_time = time.time()
        logger.debug("Set metrics.end_time to %s", self.metrics.end_time)
        self.metrics.compute()
