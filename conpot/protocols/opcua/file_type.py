# Copyright (C) 2026 MushMush Foundation
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.

"""OPC UA FileType (IEC 62541 Part 5) file transfer emulation and payload capture."""

from __future__ import annotations

import hashlib
import logging
from datetime import datetime, timezone
from typing import Any

from asyncua import Node, Server, ua
from fs.subfs import SubFS

from conpot.core.fs_utils import SubAbstractFS
from conpot.protocols.opcua.session import current_opcua_session
from conpot.utils.networking import sanitize_file_name

logger = logging.getLogger(__name__)

# Standard FileOpen modes (IEC 62541 Part 5)
MODE_READ = 0x01
MODE_WRITE = 0x02
MODE_ERASE_EXISTING = 0x04
MODE_APPEND = 0x08

DEFAULT_MAX_FILE_SIZE = 1048576  # 1 MB
DEFAULT_MAX_HANDLES_PER_SESSION = 16
DEFAULT_MAX_HANDLES_TOTAL = 100


class FileTypeHandler:
    """Manages an individual OPC UA FileType node backed by Conpot VFS and data_fs."""

    def __init__(
        self,
        server: Server,
        node: Node,
        name: str,
        vfs: SubAbstractFS,
        data_fs: SubFS,
        root_path: str = "/data/opcua/",
        data_fs_subdir: str = "opcua",
        initial_content: bytes | str = b"",
        writable: bool = True,
        mime_type: str = "application/octet-stream",
        max_file_size: int = DEFAULT_MAX_FILE_SIZE,
        max_handles_per_session: int = DEFAULT_MAX_HANDLES_PER_SESSION,
        max_handles_total: int = DEFAULT_MAX_HANDLES_TOTAL,
    ):
        self.server = server
        self.node = node
        self.name = name
        self.vfs = vfs
        self.data_fs = data_fs
        self.root_path = root_path
        self.data_fs_subdir = data_fs_subdir
        if isinstance(initial_content, str):
            self._initial_content = initial_content.encode("utf-8")
        else:
            self._initial_content = bytes(initial_content)
        self.writable = bool(writable)
        self.mime_type = str(mime_type)
        self.max_file_size = int(max_file_size)
        self.max_handles_per_session = int(max_handles_per_session)
        self.max_handles_total = int(max_handles_total)

        self.handles: dict[int, dict[str, Any]] = {}
        self._next_handle: int = 1

        self._size_node: Node | None = None
        self._writable_node: Node | None = None
        self._user_writable_node: Node | None = None
        self._open_count_node: Node | None = None
        self._mime_type_node: Node | None = None
        self._max_len_node: Node | None = None
        self._last_modified_node: Node | None = None

    async def init_nodes(self) -> None:
        """Seed file into VFS if needed, initialize FileType variables, and link RPC methods."""
        if not self.vfs.exists(self.name):
            self.vfs.writebytes(self.name, self._initial_content)

        file_size = self.vfs.getsize(self.name)
        try:
            mtime = self.vfs.getinfo(self.name, namespaces=["details"]).modified
            if mtime and mtime.tzinfo is None:
                mtime = mtime.replace(tzinfo=timezone.utc)
            elif not mtime:
                mtime = datetime.now(timezone.utc)
        except Exception:
            mtime = datetime.now(timezone.utc)

        self._size_node = await self.node.get_child("0:Size")
        await self._size_node.write_value(ua.Variant(file_size, ua.VariantType.UInt64))

        self._writable_node = await self.node.get_child("0:Writable")
        await self._writable_node.write_value(
            ua.Variant(self.writable, ua.VariantType.Boolean)
        )

        self._user_writable_node = await self.node.get_child("0:UserWritable")
        await self._user_writable_node.write_value(
            ua.Variant(self.writable, ua.VariantType.Boolean)
        )

        self._open_count_node = await self.node.get_child("0:OpenCount")
        await self._open_count_node.write_value(ua.Variant(0, ua.VariantType.UInt16))

        self._mime_type_node = await self.node.get_child("0:MimeType")
        await self._mime_type_node.write_value(
            ua.Variant(self.mime_type, ua.VariantType.String)
        )

        self._max_len_node = await self.node.get_child("0:MaxByteStringLength")
        await self._max_len_node.write_value(
            ua.Variant(self.max_file_size, ua.VariantType.UInt32)
        )

        self._last_modified_node = await self.node.get_child("0:LastModifiedTime")
        await self._last_modified_node.write_value(
            ua.Variant(mtime, ua.VariantType.DateTime)
        )

        # Link standard FileType RPC methods
        self.server.link_method(await self.node.get_child("0:Open"), self.open)
        self.server.link_method(await self.node.get_child("0:Close"), self.close)
        self.server.link_method(await self.node.get_child("0:Read"), self.read)
        self.server.link_method(await self.node.get_child("0:Write"), self.write)
        self.server.link_method(
            await self.node.get_child("0:GetPosition"), self.get_position
        )
        self.server.link_method(
            await self.node.get_child("0:SetPosition"), self.set_position
        )

    def _get_owned_handle_info(
        self, handle: int
    ) -> tuple[dict[str, Any] | None, ua.StatusCode | None]:
        """Validate handle existence and ensure the caller owns the handle."""
        info = self.handles.get(handle)
        if not info:
            return None, ua.StatusCode(ua.StatusCodes.BadInvalidArgument)

        session = current_opcua_session.get()
        if session is not None and info.get("session_id") is not None:
            if str(session.id) != info["session_id"]:
                logger.warning(
                    "OPC UA FileType handle ownership violation: handle %d owned by session %s, called by %s",
                    handle,
                    info["session_id"],
                    session.id,
                )
                return None, ua.StatusCode(ua.StatusCodes.BadInvalidArgument)
        return info, None

    async def open(self, parent: Node, mode_v: Any) -> list[ua.Variant] | ua.StatusCode:
        """OPC UA FileType Open method."""
        mode = int(mode_v.Value if isinstance(mode_v, ua.Variant) else mode_v)

        is_write = bool(mode & MODE_WRITE)
        is_erase = bool(mode & MODE_ERASE_EXISTING)
        is_append = bool(mode & MODE_APPEND)

        if is_write and not self.writable:
            return ua.StatusCode(ua.StatusCodes.BadNotWritable)

        # Enforce open handle limits (DoS protection & UInt16 OpenCount bounds)
        if len(self.handles) >= self.max_handles_total:
            logger.warning(
                "OPC UA FileType Open rejected: total open handle limit reached (%d/%d)",
                len(self.handles),
                self.max_handles_total,
            )
            return ua.StatusCode(ua.StatusCodes.BadTooManyOperations)

        session = current_opcua_session.get()
        session_id = str(session.id) if session is not None else None
        if session_id is not None:
            session_handles = sum(
                1 for h in self.handles.values() if h.get("session_id") == session_id
            )
            if session_handles >= self.max_handles_per_session:
                logger.warning(
                    "OPC UA FileType Open rejected: session %s reached open handle limit (%d/%d)",
                    session_id,
                    session_handles,
                    self.max_handles_per_session,
                )
                return ua.StatusCode(ua.StatusCodes.BadTooManyOperations)

        handle = self._next_handle
        self._next_handle += 1

        existing_data = (
            self.vfs.readbytes(self.name) if self.vfs.exists(self.name) else b""
        )

        if is_write:
            if is_erase:
                buf = bytearray()
            elif is_append:
                buf = bytearray(existing_data)
            else:
                buf = bytearray(existing_data)
            pos = len(buf) if is_append else 0
        else:
            buf = bytearray(existing_data)
            pos = 0

        self.handles[handle] = {
            "handle": handle,
            "session": session,
            "session_id": session_id,
            "mode": mode,
            "pos": pos,
            "buffer": buf,
            "is_write": is_write,
            "has_written": bool(is_erase),
        }

        if self._open_count_node:
            await self._open_count_node.write_value(
                ua.Variant(len(self.handles), ua.VariantType.UInt16)
            )

        if session is not None:
            session.log_event(
                event_type="OPCUA_FILE_OPEN",
                file=self.name,
                mode=mode,
                handle=handle,
            )
        logger.info(
            "OPC UA FileType Open: %s (mode=0x%02x, handle=%d, session=%s)",
            self.name,
            mode,
            handle,
            session_id,
        )
        return [ua.Variant(handle, ua.VariantType.UInt32)]

    async def _finalize_handle(
        self, info: dict[str, Any], session: Any, reason: str = "close"
    ) -> None:
        """Persist written data to VFS + data_fs and emit capture event."""
        handle = info.get("handle", 0)
        owner_session = info.get("session") or session
        if info["is_write"] and info["has_written"]:
            payload = bytes(info["buffer"])
            md5_hash = hashlib.md5(payload).hexdigest()

            # Update file in VFS
            self.vfs.writebytes(self.name, payload)

            # Persist upload to data_fs using the handle creator session's address
            peer_host = (
                getattr(owner_session, "source_ip", "127.0.0.1")
                if owner_session
                else "127.0.0.1"
            )
            peer_port = getattr(owner_session, "source_port", 0) if owner_session else 0
            base_filename = sanitize_file_name(self.name, peer_host, peer_port)
            data_fs_filename = base_filename
            counter = 1
            while self.data_fs.exists(data_fs_filename):
                data_fs_filename = f"{base_filename}_{counter}"
                counter += 1

            try:
                self.data_fs.writebytes(data_fs_filename, payload)
            except Exception as exc:
                logger.error("Failed writing captured payload to data_fs: %s", exc)

            if self._size_node:
                await self._size_node.write_value(
                    ua.Variant(len(payload), ua.VariantType.UInt64)
                )
            if self._last_modified_node:
                await self._last_modified_node.write_value(
                    ua.Variant(datetime.now(timezone.utc), ua.VariantType.DateTime)
                )

            if owner_session is not None:
                owner_session.log_event(
                    event_type="OPCUA_FILE_CAPTURED",
                    file=self.name,
                    handle=handle,
                    size=len(payload),
                    md5=md5_hash,
                    filename=data_fs_filename,
                    path=f"{self.data_fs_subdir}/{data_fs_filename}",
                    vfs_path=f"{self.root_path}{self.name}",
                    reason=reason,
                )
            logger.info(
                "Captured OPC UA file payload: %s (size=%d, md5=%s, data_fs=%s, reason=%s)",
                self.name,
                len(payload),
                md5_hash,
                data_fs_filename,
                reason,
            )

        if reason == "close" and owner_session is not None:
            owner_session.log_event(
                event_type="OPCUA_FILE_CLOSE",
                file=self.name,
                handle=handle,
            )

        if self._open_count_node:
            await self._open_count_node.write_value(
                ua.Variant(len(self.handles), ua.VariantType.UInt16)
            )

    async def close(
        self, parent: Node, handle_v: Any
    ) -> list[ua.Variant] | ua.StatusCode:
        """OPC UA FileType Close method."""
        handle = int(handle_v.Value if isinstance(handle_v, ua.Variant) else handle_v)
        info, err = self._get_owned_handle_info(handle)
        if err is not None:
            return err
        self.handles.pop(handle, None)

        session = info.get("session") or current_opcua_session.get()
        await self._finalize_handle(info, session, reason="close")
        return []

    async def finalize_session_handles(self, session_id: str) -> None:
        """Finalize any pending writes for a disconnected attack session."""
        matching_handles = [
            h
            for h, info in list(self.handles.items())
            if info.get("session_id") == session_id
        ]
        for handle in matching_handles:
            info = self.handles.pop(handle, None)
            if info:
                await self._finalize_handle(
                    info, info.get("session"), reason="disconnect"
                )

    async def read(
        self, parent: Node, handle_v: Any, length_v: Any
    ) -> list[ua.Variant] | ua.StatusCode:
        """OPC UA FileType Read method."""
        handle = int(handle_v.Value if isinstance(handle_v, ua.Variant) else handle_v)
        length = int(length_v.Value if isinstance(length_v, ua.Variant) else length_v)

        info, err = self._get_owned_handle_info(handle)
        if err is not None:
            return err
        if length < 0:
            return ua.StatusCode(ua.StatusCodes.BadInvalidArgument)

        length = min(length, 65536)
        pos = info["pos"]
        chunk = bytes(info["buffer"][pos : pos + length])
        info["pos"] += len(chunk)

        session = info.get("session") or current_opcua_session.get()
        if session is not None:
            session.log_event(
                event_type="OPCUA_FILE_READ",
                file=self.name,
                handle=handle,
                length=len(chunk),
                position=pos,
            )
        return [ua.Variant(chunk, ua.VariantType.ByteString)]

    async def write(
        self, parent: Node, handle_v: Any, data_v: Any
    ) -> list[ua.Variant] | ua.StatusCode:
        """OPC UA FileType Write method."""
        handle = int(handle_v.Value if isinstance(handle_v, ua.Variant) else handle_v)
        data = data_v.Value if isinstance(data_v, ua.Variant) else data_v
        if not isinstance(data, (bytes, bytearray)):
            data = bytes(data)

        info, err = self._get_owned_handle_info(handle)
        if err is not None:
            return err
        if not info["is_write"]:
            return ua.StatusCode(ua.StatusCodes.BadNotWritable)

        pos = info["pos"]
        buf = info["buffer"]
        if pos + len(data) > self.max_file_size:
            return ua.StatusCode(ua.StatusCodes.BadOutOfRange)

        if pos > len(buf):
            buf.extend(b"\x00" * (pos - len(buf)))
        buf[pos : pos + len(data)] = data
        info["pos"] += len(data)
        info["has_written"] = True

        session = info.get("session") or current_opcua_session.get()
        if session is not None:
            session.log_event(
                event_type="OPCUA_FILE_WRITE",
                file=self.name,
                handle=handle,
                length=len(data),
                position=pos,
            )
        return []

    async def get_position(
        self, parent: Node, handle_v: Any
    ) -> list[ua.Variant] | ua.StatusCode:
        """OPC UA FileType GetPosition method."""
        handle = int(handle_v.Value if isinstance(handle_v, ua.Variant) else handle_v)
        info, err = self._get_owned_handle_info(handle)
        if err is not None:
            return err
        return [ua.Variant(info["pos"], ua.VariantType.UInt64)]

    async def set_position(
        self, parent: Node, handle_v: Any, pos_v: Any
    ) -> list[ua.Variant] | ua.StatusCode:
        """OPC UA FileType SetPosition method."""
        handle = int(handle_v.Value if isinstance(handle_v, ua.Variant) else handle_v)
        pos = int(pos_v.Value if isinstance(pos_v, ua.Variant) else pos_v)

        info, err = self._get_owned_handle_info(handle)
        if err is not None:
            return err
        if pos < 0 or pos > len(info["buffer"]):
            return ua.StatusCode(ua.StatusCodes.BadInvalidArgument)

        info["pos"] = pos
        return []

    def close_all(self) -> None:
        """Cleanly close all open handles upon server shutdown."""
        self.handles.clear()


class OPCUAFileManager:
    """Manages the FileType collection in the OPC UA address space."""

    def __init__(
        self,
        server: Server,
        idx: int,
        vfs: SubAbstractFS,
        data_fs: SubFS,
        root_path: str = "/data/opcua/",
        data_fs_subdir: str = "opcua",
        files_config: list[dict[str, Any]] | None = None,
        max_file_size: int = DEFAULT_MAX_FILE_SIZE,
        max_handles_per_session: int = DEFAULT_MAX_HANDLES_PER_SESSION,
        max_handles_total: int = DEFAULT_MAX_HANDLES_TOTAL,
    ):
        self.server = server
        self.idx = idx
        self.vfs = vfs
        self.data_fs = data_fs
        self.root_path = root_path
        self.data_fs_subdir = data_fs_subdir
        self.files_config = list(files_config or [])
        self.max_file_size = int(max_file_size)
        self.max_handles_per_session = int(max_handles_per_session)
        self.max_handles_total = int(max_handles_total)
        self.handlers: dict[str, FileTypeHandler] = {}
        self.folder: Node | None = None

    async def setup(self) -> Node:
        """Create the Files folder and seed FileType nodes backed by VFS."""
        self.folder = await self.server.nodes.objects.add_object(self.idx, "Files")

        configs = list(self.files_config)
        seen_names = {
            str(item.get("name", "")).strip() for item in configs if item.get("name")
        }

        # If no files specified in template, seed default decoys
        if not configs and not self.vfs.listdir("."):
            configs = [
                {
                    "name": "firmware.bin",
                    "content": "CONPOT_PLC_FW_V2.1.0",
                    "writable": True,
                    "mime_type": "application/octet-stream",
                },
                {
                    "name": "configuration.xml",
                    "content": "<DeviceConfiguration><StationId>Plant-01</StationId></DeviceConfiguration>",
                    "writable": True,
                    "mime_type": "text/xml",
                },
            ]
            seen_names = {"firmware.bin", "configuration.xml"}

        # Register configured files
        for item in configs:
            name = str(item.get("name", "")).strip()
            if not name:
                continue
            content = item.get("content", "")
            writable = bool(item.get("writable", True))
            mime_type = str(item.get("mime_type", "application/octet-stream"))

            file_node = await self.folder.add_object(
                self.idx, name, objecttype=ua.NodeId(ua.ObjectIds.FileType, 0)
            )
            handler = FileTypeHandler(
                server=self.server,
                node=file_node,
                name=name,
                vfs=self.vfs,
                data_fs=self.data_fs,
                root_path=self.root_path,
                data_fs_subdir=self.data_fs_subdir,
                initial_content=content,
                writable=writable,
                mime_type=mime_type,
                max_file_size=self.max_file_size,
                max_handles_per_session=self.max_handles_per_session,
                max_handles_total=self.max_handles_total,
            )
            await handler.init_nodes()
            self.handlers[name] = handler
            logger.info("Added OPC UA FileType node from config: %s", name)

        # Also expose any pre-existing files present in VFS (e.g. from add_src or data.tar)
        for vfs_file in self.vfs.listdir("."):
            if vfs_file in seen_names or not self.vfs.isfile(vfs_file):
                continue
            file_node = await self.folder.add_object(
                self.idx, vfs_file, objecttype=ua.NodeId(ua.ObjectIds.FileType, 0)
            )
            handler = FileTypeHandler(
                server=self.server,
                node=file_node,
                name=vfs_file,
                vfs=self.vfs,
                data_fs=self.data_fs,
                root_path=self.root_path,
                data_fs_subdir=self.data_fs_subdir,
                initial_content=b"",
                writable=True,
                mime_type="application/octet-stream",
                max_file_size=self.max_file_size,
                max_handles_per_session=self.max_handles_per_session,
                max_handles_total=self.max_handles_total,
            )
            await handler.init_nodes()
            self.handlers[vfs_file] = handler
            logger.info("Added OPC UA FileType node from VFS: %s", vfs_file)

        return self.folder

    async def session_disconnected(self, session_id: str) -> None:
        """Finalize any open handles when an attack session disconnects."""
        for handler in self.handlers.values():
            await handler.finalize_session_handles(session_id)

    def close_all_handles(self) -> None:
        """Close all open handles across all files."""
        for handler in self.handlers.values():
            handler.close_all()
