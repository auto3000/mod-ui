# coding: utf-8

# Copyright 2017 pedalpi
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import errno
import functools
import socket
from tornado import ioloop, iostream

class HMI_socket(HMI):
    def send_request():
        sp.write(b"Hello my friend JFD protocol\r\n\r\n")

    def connection_ready(sock, fd, events):
        while True:
            try:
                connection, address = sock.accept()
            except socket.error, e:
                if e[0] not in (errno.EWOULDBLOCK, errno.EAGAIN):
                    raise
                return
            else:
                logging.error('[hmi_socket] connection from %s' % repr(address))
                connection.setblocking(0)
                self.sp = tornado.iostream.IOStream(connection)

    # overrides super class
    def init(self, callback):
        self.sp = FakeHMI()

        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM, 0)
            sock.setblocking(0)
            sock.bind(("", 9999))
            sock.listen(1)
            sp = tornado.iostream.IOStream(sock)
        except Exception as e:
            print("ERROR: Failed to open HMI socket port, error was:\n%s" % e)
            return

        def clear_callback(ok):
            callback()

        # calls ping until ok is received
        def ping_callback(ok):
            if ok:
                self.clear(clear_callback)
            else:
                self.ioloop.add_timeout(timedelta(seconds=1), lambda:self.ping(ping_callback))

        self.ping(ping_callback)
        self.checker()
