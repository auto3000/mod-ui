# coding: utf-8

# Copyright 2017 pedalpiII
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
import threading



class EchoServer(TCPServer):
    def __init__(self, my_ioloop, my_hmisocket, callback):
        super().__init__(my_ioloop)
        self.callback = callback
        self.my_hmisocket = my_hmisocket

    @gen.coroutine
    def handle_stream(self, stream, address):
        #threading.Thread(target=self.my_hmisocket.handle_stream, args=(stream, address)).start()
        #yield
        logging.info('[EchoServer] connection from %s' % repr(address))
        yield self.my_hmisocket.handle_stream(stream, address)


class HMISocket(HMI):

    def __init__(self, port, callback):
        print("JFD launch HMISocket on port", port)
        self.sp = None #FakeHMI().sp
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
            #server.start(0)  # Forks multiple sub-processes
        except Exception as e:
            print("ERROR: Failed to open HMI socket port, error was: %s" % e)
            return


    @gen.coroutine
    def handle_stream(self, stream, address):
        def clear_callback(ok):
            self.callback()

        # calls ping until ok is received
        def ping_callback(ok):
            logging.error('[hmi_socket] ping_callback %s' % ok)
            if ok:
                self.clear(clear_callback)
            else:
                self.ioloop.add_timeout(timedelta(seconds=1), lambda:self.ping(self.ping_callback))

#        def no_callback():
#            pass
        #stream.write(b"Hello my friend JFD protocol\r\n\r\n", no_callback)
        logging.info('[hmi_socket] connection from %s' % repr(address))
        #self.sp = SerialIOStream(stream)
        self.sp = stream
        self.ping(ping_callback)
        #logging.info('[hmi_socket] ping passed')
        #data = yield stream.read_until(b"\0")
        self.checker()
        #logging.info('[hmi_socket] checker passed')

        while False:
        #self.sp.write(b"Hello my friend JFD protocol2222\r\n\r\n")
            try:
                data = yield stream.read_until(b"\n")
                logging.info('[hmi_socket] receive %s' % data)
                yield stream.write(data)
            except StreamClosedError:
                break
        #self.sp = FakeHMI().sp
