# Copyright (C) 2013 MushMush Foundation
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.

import argparse
import asyncio
import logging
import os
import pwd
import grp
import signal
import sys
from configparser import ConfigParser, NoSectionError, NoOptionError

import conpot
import conpot.core as conpot_core
from conpot.core.protocol_startup import start_services
from conpot.core.templates import (
    format_template_list,
    list_available_templates,
    load_base_template,
    resolve_template_directory,
)
from conpot.utils import ext_ip
from conpot.utils.logging import setup_logging

logger = logging.getLogger()
package_directory = os.path.dirname(os.path.abspath(conpot.__file__))
core_interface = conpot_core.get_interface()


def logo():
    print("""
                       _
   ___ ___ ___ ___ ___| |_
  |  _| . |   | . | . |  _|
  |___|___|_|_|  _|___|_|
              |_|

  Version {0}
  MushMush Foundation
""".format(conpot.__version__))


def drop_privileges(uid_name=None, gid_name=None):
    if uid_name is None:
        uid_name = "nobody"

    try:
        wanted_user = pwd.getpwnam(uid_name)
    except KeyError:
        logger.exception(
            'Cannot drop privileges: user "{}" does not exist.'.format(uid_name)
        )
        sys.exit(1)

    if gid_name is None:
        gid_name = grp.getgrgid(wanted_user.pw_gid).gr_name

    try:
        wanted_group = grp.getgrnam(gid_name)
    except KeyError:
        logger.exception(
            'Cannot drop privileges: group "{}" does not exist.'.format(gid_name)
        )
        sys.exit(1)

    logger.debug(
        'Attempting to drop privileges to "{}:{}"'.format(
            wanted_user.pw_name, wanted_group.gr_name
        )
    )
    os.setgid(wanted_group.gr_gid)
    os.setuid(wanted_user.pw_uid)
    new_user = pwd.getpwuid(os.getuid())
    new_group = grp.getgrgid(os.getgid())
    logger.info(
        'Privileges dropped, running as "{}:{}"'.format(
            new_user.pw_name, new_group.gr_name
        )
    )


async def _async_main(args, config, root_template_directory, template, template_base):
    loop = asyncio.get_running_loop()
    session_manager = conpot_core.get_sessionManager()
    session_manager.attach_event_loop(loop)

    if isinstance(template, dict):
        conpot_core.get_databus().initialize(template)
    else:
        conpot_core.get_databus().initialize(template_base)

    fs_url = config.get("virtual_file_system", "fs_url")
    data_fs_url = config.get("virtual_file_system", "data_fs_url")
    if os.path.isdir(args.temp_dir):
        temp_dir = args.temp_dir
    else:
        temp_dir = os.path.join(conpot.__path__[0], "ConpotTempFS")
        logger.info("Temp directory not specified, will create at: {}".format(temp_dir))
        if not os.path.exists(temp_dir):
            os.mkdir(temp_dir)
    if fs_url == "default" or data_fs_url == "default":
        logger.warning("No file system configured, using default paths.")
        fs_url, data_fs_url = None, None
    else:
        logger.info(
            "Serving {} as file system. File uploads will be kept at : {}".format(
                fs_url, data_fs_url
            )
        )
    conpot_core.initialize_vfs(fs_url, data_fs_url, temp_dir)

    public_ip = None
    if config.getboolean("fetch_public_ip", "enabled"):
        public_ip = await loop.run_in_executor(None, ext_ip.get_ext_ip, config)

    servers = await start_services(
        root_template_directory,
        package_directory,
        config,
        args,
        template,
        session_manager,
        public_ip,
    )

    if not servers:
        logger.error("No services started.")
        return

    stop_event = asyncio.Event()

    def _request_shutdown():
        logger.info("Shutdown signal received")
        stop_event.set()

    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, _request_shutdown)
        except NotImplementedError:
            # Windows / restricted environments
            pass

    try:
        await stop_event.wait()
    finally:
        logging.info("Stopping Conpot")
        for server, handle in servers:
            logging.debug("Shutting down %s", handle.name)
            try:
                server.stop()
            except Exception:
                logger.exception("Error stopping %s", handle.name)
            # Await on this loop — handle.get()/join() deadlocks here because they
            # block the loop thread with run_coroutine_threadsafe().result().
            await handle.wait(timeout=15)
        conpot_core.close_fs()


def main():
    logo()

    parser = argparse.ArgumentParser()

    parser.add_argument(
        "-t",
        "--template",
        help="Name of one of the supplied templates, or the full path to a custom template.",
        default="",
    )
    parser.add_argument(
        "-f",
        "--force",
        help="Force use testing config.",
        metavar="testing.cfg",
        action="store_const",
        const=True,
        default=False,
    )
    parser.add_argument(
        "-c",
        "--config",
        help="The configuration file to use",
        metavar="conpot.cfg",
    )

    parser.add_argument(
        "-l", "--logfile", help="The logfile to use", default="conpot.log"
    )
    parser.add_argument(
        "-m", "--mibcache", help="Cache directory for compiled PySNMP MIB files"
    )
    parser.add_argument(
        "--temp_dir",
        help="Directory where all conpot vfs related files would be kept.",
        default="ConpotTempFS",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        default=False,
        help="Logs debug messages.",
    )
    args = parser.parse_args()

    setup_logging(args.logfile, args.verbose)

    core_interface.config = ConfigParser(os.environ)
    config = core_interface.config

    if os.getuid() == 0:
        if not args.force:
            logger.critical(
                "Can't start conpot with root. Please ref user docs for more info."
            )
            sys.exit(3)
        else:
            logger.warning(
                "Running conpot with root. Running conpot with root isn't recommended. "
            )

    if os.getuid() == 0:
        try:
            conpot_user = config.get("daemon", "user")
        except NoSectionError, NoOptionError:
            conpot_user = None

        try:
            conpot_group = config.get("daemon", "group")
        except NoSectionError, NoOptionError:
            conpot_group = None
        drop_privileges(conpot_user, conpot_group)

    if args.force:
        args.config = os.path.join(package_directory, "testing.cfg")
        logger.warning("--force option specified. Using testing configuration")
        config.read(args.config)
    else:
        if not (args.config and args.template):
            print(
                "Invalid arguments supplied. Please check that you pass both template and config arguments before"
                " running Conpot"
            )
            sys.exit(3)
        try:
            if not os.path.isfile(os.path.join(package_directory, args.config)):
                raise FileNotFoundError("Config file not found!")
            args.config = os.path.join(package_directory, args.config)
            logger.info("Config file found!")
            config.read(args.config)
        except FileNotFoundError:
            logger.exception(
                "\nCould not find config file!\nUse -f option to try the test configuration"
            )
            sys.exit(1)

    if not args.template:
        templates = list_available_templates(package_directory)
        print(format_template_list(templates))
        sys.exit(0)

    root_template_directory = resolve_template_directory(
        args.template, package_directory
    )
    if root_template_directory is None:
        logger.error("Template not found: {}".format(args.template))
        sys.exit(1)

    if not os.path.isfile(args.config):
        logger.error("Config not found: {}".format(args.config))
        sys.exit(1)

    logger.info("Starting Conpot using template: {}".format(root_template_directory))
    logger.info("Starting Conpot using configuration found in: {}".format(args.config))

    template, template_base = load_base_template(
        root_template_directory, package_directory
    )

    try:
        asyncio.run(
            _async_main(args, config, root_template_directory, template, template_base)
        )
    except KeyboardInterrupt:
        logging.info("Stopping Conpot")


if __name__ == "__main__":
    main()
