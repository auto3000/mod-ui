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
import functools
import os, json, logging

from tornado import ioloop, iostream
from tornado.tcpserver import TCPServer
from tornado.iostream import StreamClosedError
from tornado import gen

from mod.hmi import HMI, SerialIOStream
from mod.development import FakeHMI

class EchoServer(TCPServer):
    def __init__(self, my_ioloop, my_hmisocket, callback):
        super().__init__(my_ioloop)
        self.callback = callback
        self.my_hmisocket = my_hmisocket

    @gen.coroutine
    def handle_stream(self, stream, address):
        self.my_hmisocket.handle_stream(stream, address)


class HMISocket(HMI):

    def __init__(self, port, callback):
        print("JFD launch HMISocket on port", port)
        self.sp = FakeHMI().sp
        self.port = port
        self.queue = []
        self.queue_idle = True
        self.initialized = False
        self.ioloop = ioloop.IOLoop.instance()
        self.callback = callback
        self.init()

    # overrides super class
    def init(self):

        try:
            server = EchoServer(ioloop.IOLoop.instance(), self, self.callback)
            server.listen(self.port)
        except Exception as e:
            print("ERROR: Failed to open HMI socket port, error was: %s" % e)
            return

    def clear_callback(ok):
        self.callback()

    # calls ping until ok is received
    def ping_callback(ok):
        logging.error('[hmi_socket] ping_callback %s' % ok)
        if ok:
            self.clear(self.clear_callback)
        else:
            self.ioloop.add_timeout(timedelta(seconds=1), lambda:self.ping(self.ping_callback))

    def handle_stream(self, stream, address):
        logging.info('[hmi_socket] connection from %s' % repr(address))
        self.sp = SerialIOStream(stream)
        #while True:
        stream.write(b"Hello my friend JFD protocol\r\n\r\n")
        #    try:
        #        data = yield stream.read_until(b"\n")
        #        yield stream.write(data)
        #    except StreamClosedError:
        #        break
        #self.sp = FakeHMI().sp
        #self.ping(self.ping_callback)
        self.clear(self.clear_callback)
        self.checker()
