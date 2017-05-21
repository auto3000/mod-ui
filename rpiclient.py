#!/usr/bin/env python3

import sys
import os.path
import tornado.ioloop
import tornado.web
import RPi.GPIO as GPIO
from time import sleep
from tornado.iostream import PipeIOStream
from tornado import ioloop, iostream
from tornado.tcpserver import TCPServer
from tornado.tcpclient import TCPClient

from tornado.iostream import StreamClosedError
from tornado import gen
import csv
#mod-ui hmi server port
PORT = 9999

#Initialize Raspberry PI GPIO
GPIO.setmode(GPIO.BOARD)

# #define LCD_SETCGRAMADDR 0x40
#// Allows us to fill the first 8 CGRAM locations
#// with custom characters
#void LiquidCrystal_I2C::createChar(uint8_t location, uint8_t charmap[]) {
#	location &= 0x7; // we only have 8 locations 0-7
#	command(LCD_SETCGRAMADDR | (location << 3));
#	for (int i=0; i<8; i++) {
#		write(charmap[i]);
#	}
#}
#uint8_t bell[8]  = {0x4, 0xe, 0xe, 0xe, 0x1f, 0x0, 0x4};
#uint8_t note[8]  = {0x2, 0x3, 0x2, 0xe, 0x1e, 0xc, 0x0};
#uint8_t clock[8] = {0x0, 0xe, 0x15, 0x17, 0x11, 0xe, 0x0};
#uint8_t heart[8] = {0x0, 0xa, 0x1f, 0x1f, 0xe, 0x4, 0x0};
#uint8_t duck[8]  = {0x0, 0xc, 0x1d, 0xf, 0xf, 0x6, 0x0};
#uint8_t check[8] = {0x0, 0x1 ,0x3, 0x16, 0x1c, 0x8, 0x0};
#uint8_t cross[8] = {0x0, 0x1b, 0xe, 0x4, 0xe, 0x1b, 0x0};
#uint8_t retarrow[8] = {	0x1, 0x1, 0x5, 0x9, 0x1f, 0x8, 0x4};

class LCD:
	# commands
	LCD_CLEARDISPLAY 		= 0x01
	LCD_RETURNHOME 		    = 0x02
	LCD_ENTRYMODESET 		= 0x04
	LCD_DISPLAYCONTROL 		= 0x08
	LCD_CURSORSHIFT 		= 0x10
	LCD_FUNCTIONSET 		= 0x20
	LCD_SETCGRAMADDR 		= 0x40
	LCD_SETDDRAMADDR 		= 0x80

	# flags for display entry mode
	LCD_ENTRYRIGHT 		= 0x00
	LCD_ENTRYLEFT 		= 0x02
	LCD_ENTRYSHIFTINCREMENT 	= 0x01
	LCD_ENTRYSHIFTDECREMENT 	= 0x00

	# flags for display on/off control
	LCD_DISPLAYON 		= 0x04
	LCD_DISPLAYOFF 		= 0x00
	LCD_CURSORON 		= 0x02
	LCD_CURSOROFF 		= 0x00
	LCD_BLINKON 		= 0x01
	LCD_BLINKOFF 		= 0x00

	# flags for display/cursor shift
	LCD_DISPLAYMOVE 	= 0x08
	LCD_CURSORMOVE 		= 0x00

	# flags for display/cursor shift
	LCD_DISPLAYMOVE 	= 0x08
	LCD_CURSORMOVE 		= 0x00
	LCD_MOVERIGHT 		= 0x04
	LCD_MOVELEFT 		= 0x00

	# flags for function set
	LCD_8BITMODE 		= 0x10
	LCD_4BITMODE 		= 0x00
	LCD_2LINE 			= 0x08
	LCD_1LINE 			= 0x00
	LCD_5x10DOTS 		= 0x04
	LCD_5x8DOTS 		= 0x00

	def __init__(self, pin_rs=27, pin_e=22, pins_db=[25, 24, 23, 18], GPIO = None):
		# Emulate the old behavior of using RPi.GPIO if we haven't been given
		# an explicit GPIO interface to use
		if not GPIO:
			import RPi.GPIO as GPIO
			self.GPIO = GPIO
			self.pin_rs = pin_rs
			self.pin_e = pin_e
			self.pins_db = pins_db

			self.used_gpio = self.pins_db[:]
			self.used_gpio.append(pin_e)
			self.used_gpio.append(pin_rs)

			self.GPIO.setwarnings(False)
			self.GPIO.setmode(GPIO.BCM)
			self.GPIO.setup(self.pin_e, GPIO.OUT)
			self.GPIO.setup(self.pin_rs, GPIO.OUT)

			for pin in self.pins_db:
				self.GPIO.setup(pin, GPIO.OUT)

		self.write4bits(0x33) # initialization
		self.write4bits(0x32) # initialization
		self.write4bits(0x28) # 2 line 5x7 matrix
		self.write4bits(0x0C) # turn cursor off 0x0E to enable cursor
		self.write4bits(0x06) # shift cursor right

		self.displaycontrol = self.LCD_DISPLAYON | self.LCD_CURSOROFF | self.LCD_BLINKOFF

		self.displayfunction = self.LCD_4BITMODE | self.LCD_1LINE | self.LCD_5x8DOTS
		self.displayfunction |= self.LCD_2LINE

		""" Initialize to default text direction (for romance languages) """
		self.displaymode =  self.LCD_ENTRYLEFT | self.LCD_ENTRYSHIFTDECREMENT
		self.write4bits(self.LCD_ENTRYMODESET | self.displaymode) #  set the entry mode

		self.clear()

	def begin(self, cols, lines):
		if (lines > 1):
			self.numlines = lines
			self.displayfunction |= self.LCD_2LINE
			self.currline = 0

	def home(self):
		self.write4bits(self.LCD_RETURNHOME) # set cursor position to zero
		self.delayMicroseconds(3000) # this command takes a long time!

	def clear(self):
		self.write4bits(self.LCD_CLEARDISPLAY) # command to clear display
		self.delayMicroseconds(3000)	# 3000 microsecond sleep, clearing the display takes a long time

	def setCursor(self, col, row):
		self.row_offsets = [ 0x00, 0x40, 0x14, 0x54 ]

		if ( row > self.numlines ):
			row = self.numlines - 1 # we count rows starting w/0

		self.write4bits(self.LCD_SETDDRAMADDR | (col + self.row_offsets[row]))

	def noDisplay(self):
		# Turn the display off (quickly)
		self.displaycontrol &= ~self.LCD_DISPLAYON
		self.write4bits(self.LCD_DISPLAYCONTROL | self.displaycontrol)

	def display(self):
		# Turn the display on (quickly)
		self.displaycontrol |= self.LCD_DISPLAYON
		self.write4bits(self.LCD_DISPLAYCONTROL | self.displaycontrol)

	def noCursor(self):
		# Turns the underline cursor on/off
		self.displaycontrol &= ~self.LCD_CURSORON
		self.write4bits(self.LCD_DISPLAYCONTROL | self.displaycontrol)

	def cursor(self):
		# Cursor On
		self.displaycontrol |= self.LCD_CURSORON
		self.write4bits(self.LCD_DISPLAYCONTROL | self.displaycontrol)

	def noBlink(self):
		# Turn on and off the blinking cursor
		self.displaycontrol &= ~self.LCD_BLINKON
		self.write4bits(self.LCD_DISPLAYCONTROL | self.displaycontrol)

	def noBlink(self):
		# Turn on and off the blinking cursor
		self.displaycontrol &= ~self.LCD_BLINKON
		self.write4bits(self.LCD_DISPLAYCONTROL | self.displaycontrol)

	def DisplayLeft(self):
		# These commands scroll the display without changing the RAM
		self.write4bits(self.LCD_CURSORSHIFT | self.LCD_DISPLAYMOVE | self.LCD_MOVELEFT)

	def scrollDisplayRight(self):
		# These commands scroll the display without changing the RAM
		self.write4bits(self.LCD_CURSORSHIFT | self.LCD_DISPLAYMOVE | self.LCD_MOVERIGHT);

	def leftToRight(self):
		# This is for text that flows Left to Right
		self.displaymode |= self.LCD_ENTRYLEFT
		self.write4bits(self.LCD_ENTRYMODESET | self.displaymode);

	def rightToLeft(self):
		# This is for text that flows Right to Left
		self.displaymode &= ~self.LCD_ENTRYLEFT
		self.write4bits(self.LCD_ENTRYMODESET | self.displaymode)

	def autoscroll(self):
		# This will 'right justify' text from the cursor
		self.displaymode |= self.LCD_ENTRYSHIFTINCREMENT
		self.write4bits(self.LCD_ENTRYMODESET | self.displaymode)

	def noAutoscroll(self):
		# This will 'left justify' text from the cursor
		self.displaymode &= ~self.LCD_ENTRYSHIFTINCREMENT
		self.write4bits(self.LCD_ENTRYMODESET | self.displaymode)

	def write4bits(self, bits, char_mode=False):
		# Send command to LCD
		self.delayMicroseconds(1000) # 1000 microsecond sleep
		bits=bin(bits)[2:].zfill(8)
		self.GPIO.output(self.pin_rs, char_mode)
		for pin in self.pins_db:
			self.GPIO.output(pin, False)
		for i in range(4):
			if bits[i] == "1":
				self.GPIO.output(self.pins_db[::-1][i], True)
		self.pulseEnable()
		for pin in self.pins_db:
			self.GPIO.output(pin, False)
		for i in range(4,8):
			if bits[i] == "1":
				self.GPIO.output(self.pins_db[::-1][i-4], True)
		self.pulseEnable()

	def delayMicroseconds(self, microseconds):
		seconds = microseconds / float(1000000)	# divide microseconds by 1 million for seconds
		sleep(seconds)

	def pulseEnable(self):
		self.GPIO.output(self.pin_e, False)
		self.delayMicroseconds(1)		# 1 microsecond pause - enable pulse must be > 450ns
		self.GPIO.output(self.pin_e, True)
		self.delayMicroseconds(1)		# 1 microsecond pause - enable pulse must be > 450ns
		self.GPIO.output(self.pin_e, False)
		self.delayMicroseconds(1)		# commands need > 37us to settle

	def message(self, text):
		# Send string to LCD. Newline wraps to second line
		print("message:\n%s" % text)
		for char in text:
			if char == '\n':
				self.write4bits(0xC0) # next line
			else:
				self.write4bits(ord(char),True)

	def destroy(self):
		print("clean up used_gpio")
		self.GPIO.cleanup(self.used_gpio)


class FakeGPIO(object):
	def output(self, a,b):
		pass

	def cleanup(self, x):
		pass

class FakeLCD(LCD):
	def __init__(self, pin_rs=27, pin_e=22, pins_db=[25, 24, 23, 18], GPIO = None):
		self.GPIO = FakeGPIO()
		self.pin_rs = None
		self.pin_e = None
		self.pins_db = [None, None, None, None]
		self.used_gpio = [None]
		return

class RotaryEncoder:

	CLOCKWISE=1
	ANTICLOCKWISE=2
	BUTTONDOWN=3
	BUTTONUP=4

	rotary_a = 0
	rotary_b = 0
	rotary_c = 0
	last_state = 0
	privDirection = 0
	direction = 0

	# Initialise rotary encoder object
	def __init__(self,pinA,pinB,button,callback):
		self.pinA = pinA
		self.pinB = pinB
		self.button = button
		self.callback = callback

		#GPIO.setmode(GPIO.BCM)

		# The following lines enable the internal pull-up resistors
		# on version 2 (latest) boards
		GPIO.setwarnings(False)
		GPIO.setup(self.pinA, GPIO.IN, pull_up_down=GPIO.PUD_UP)
		GPIO.setup(self.pinB, GPIO.IN, pull_up_down=GPIO.PUD_UP)
		GPIO.setup(self.button, GPIO.IN, pull_up_down=GPIO.PUD_UP) #sure ?

		# For version 1 (old) boards comment out the above four lines
		# and un-comment the following 3 lines
		#GPIO.setup(self.pinA, GPIO.IN)
		#GPIO.setup(self.pinB, GPIO.IN)
		#GPIO.setup(self.button, GPIO.IN)

		# Add event detection to the GPIO inputs
		GPIO.add_event_detect(self.pinA, GPIO.FALLING, callback=self.switch_event)
		GPIO.add_event_detect(self.pinB, GPIO.FALLING, callback=self.switch_event)
		GPIO.add_event_detect(self.button, GPIO.BOTH, callback=self.button_event, bouncetime=200)
		return

	# Call back routine called by switch events
	def switch_event(self,switch):
		if GPIO.input(self.pinA):
			self.rotary_a = 1
		else:
			self.rotary_a = 0

		if GPIO.input(self.pinB):
			self.rotary_b = 1
		else:
			self.rotary_b = 0

		self.rotary_c = self.rotary_a ^ self.rotary_b
		new_state = self.rotary_a * 4 + self.rotary_b * 2 + self.rotary_c * 1

		delta1 = (new_state - self.last_state) % 4
		self.last_state = new_state
		event = 0

#		print delta1 , " - priv: " , self.privDirection
		if delta1 == 1:
			if self.direction == self.CLOCKWISE:
				# print "Clockwise"
#				if self.privDirection == self.CLOCKWISE:
				event = self.direction
			else:
				self.direction = self.CLOCKWISE
		elif delta1 == 3:
			if self.direction == self.ANTICLOCKWISE:
				# print "Anticlockwise"
#				if self.privDirection == self.ANTICLOCKWISE:
				event = self.direction
			else:
				self.direction = self.ANTICLOCKWISE

		self.privDirection = delta1
		if event > 0:
			self.callback(event)
		return


	# Push button up event
	def button_event(self,button):
		if GPIO.input(button):
			event = self.BUTTONUP
		else:
			event = self.BUTTONDOWN
		self.callback(event)
		return

	# Get a switch state
	def getSwitchState(self, switch):
		return  GPIO.input(switch)

class FakeRotaryEncoder(RotaryEncoder):
	def __init__(self,pinA,pinB,button,callback):
		self.callback = callback
		pass

	def getSwitchState(self, switch):
		return 0

# End of RotaryEncoder class

def asyncRotaryEncoderCallback(event):
	global ssocket
	print("JFD stream.write for event=", event)
	return


def rotaryEncoderCallback(event):
	print("rotaryEncoderCallback with ", event)
	main_loop.add_callback(callback=lambda: asyncRotaryEncoderCallback(event))
	return



class RpiProtocol(object):
    COMMANDS = {
        "ping": [],
        "control_rm": [int, str],
        "ui_dis": [],
        "ui_con": [],
        "bank_config": [int, int, int, int, int], #hw_type, hw_id, actuator_type, actuator_id, action
        "initial_state": [int, int, str], # bank_id, pedalboard_id, pedalboards #variadic couple 0 str0 1 str1 ...
        "control_add": [int, str, str, int, str, float, float, float, int, int, int, int, int, int, int ],
		"control_clean": [int, int, int, int]
		# instance_id, port, label, var_type, unit, value, min, max, steps, hw_type, hw_id, actuator_type, actuator_id, n_controllers, index, options
    }

    COMMANDS_FUNC = {}

    RESPONSES = [
        "resp", "few aguments", "many arguments", "not found"
    ]

    @classmethod
    def register_cmd_callback(cls, cmd, func):
        if cmd not in cls.COMMANDS.keys():
            raise ValueError("Command %s is not registered" % cmd)

        cls.COMMANDS_FUNC[cmd] = func

    def __init__(self, msg):
        self.msg = msg.replace("\0", "").strip()
        self.cmd = ""
        self.args = []
        self.parse()

    def is_resp(self):
        return any(self.msg.startswith(resp) for resp in self.RESPONSES)

    def run_cmd(self, callback):
        if not self.cmd:
            callback("-1003") # TODO: proper error handling
            return

        if not self.cmd in self.COMMANDS_FUNC.keys():
            print(str(self.COMMANDS_FUNC.keys()) + " xxx " + self.cmd)
            callback("-1004") # TODO: proper error handling
            return
        args = [callback] + self.args
        self.COMMANDS_FUNC[self.cmd](*args)

    def process_resp(self, datatype):
        if "resp" in self.msg:
            resp = self.msg.replace("resp ", "")
            return process_resp(resp, datatype)
        return self.msg

    def parse(self):
        if self.is_resp():
            return

        #cmd = self.msg.split()
        for line in csv.reader([self.msg], delimiter=' ', quotechar='"'):
            cmd = line
        if not cmd or cmd[0] not in self.COMMANDS.keys():
            raise ProtocolError("not found") # Command not found

        try:
            self.cmd = cmd[0]
            #self.args = [ typ(arg) for typ, arg in zip(self.COMMANDS[self.cmd], cmd[1:]) ]
            self.args = [ typ(arg) for typ, arg in zip(self.COMMANDS[self.cmd], cmd[1:]) ]
            self.args = cmd[1:]
            #print ("xxx ", self.args)
            #if not all(str(a) for a in self.args):
            #    raise ValueError
        except ValueError:
            print ("wrong arg type for: %s %s" % (self.cmd, self.args))
            raise ProtocolError("wrong arg type for: %s %s" % (self.cmd, self.args))

class PedalModel(object):

	def __init__(self, display):
		self.display = display
		self.controller = None # it must be set at construction asap
		return

	def change_pedalboards(self, counter):
		self.pedalboard_id = (self.pedalboard_id + counter) % self.pedalboards_len
		new_pedalboard = (self.pedalboard_id + 1) % (self.pedalboards_len + 1)
		print (new_pedalboard)
		print (self.pedalboard_id)
		print (self.pedalboards)
		self.display.message("SELECT BOARD %02d\n%16s" % (new_pedalboard, self.pedalboards[self.pedalboard_id]))
		self.controller.set_pedalboard(self.bank_id, self.pedalboard_id)
		return

	def set_initial_state(self, bank_id, pedalboard_id, pedalboards):
		self.bank_id = int(bank_id)
		self.pedalboard_id = 0 #Force pedalboard to first entry
		self.pedalboards_len = int(pedalboard_id) - 1 # ignore the last entry DEFAULT
		self.pedalboards = []
		for i in range(0, self.pedalboards_len + 1): # recopy only text elements
			self.pedalboards = self.pedalboards + [ pedalboards[2*i] ]
		self.change_pedalboards(0)
		return

class SocketService(object):
	def __init__(self, pedalmodel):
		self.pedalmodel = pedalmodel
		self.setup()
		RpiProtocol.register_cmd_callback("ping", self.ping)
		RpiProtocol.register_cmd_callback("ui_con", self.ui_connected)
		RpiProtocol.register_cmd_callback("ui_dis", self.ui_disconnected)
		RpiProtocol.register_cmd_callback("control_rm", self.control_rm)
		RpiProtocol.register_cmd_callback("bank_config", self.bank_config)
		RpiProtocol.register_cmd_callback("initial_state", self.initial_state)
		RpiProtocol.register_cmd_callback("control_add", self.control_add)
		return

	def ui_connected(self, callback):
		print("ignore ui connected")
		callback(True)

	def ping(self, callback):
		callback(True)

	def ui_disconnected(self, callback):
		print("ignore ui disconnected")
		callback(True)

	def control_rm(self, callback, instance_id, port):
		print("ignore control_rm command")
		callback(True)

	def bank_config(self, callback, hw_type, hw_id, actuator_type, actuator_id, action):
		print("ignore bank_config command")
		callback(True)

	def initial_state(self, callback, bank_id, pedalboard_id, *pedalboards):
		print("initial_state command bank_id=" + str(bank_id) + " pedalboard_id=" + str(pedalboard_id) + " pedalboards=" + str(pedalboards) )
		self.pedalmodel.set_initial_state( bank_id, pedalboard_id, pedalboards)
		callback(True)

	def control_add(self, callback, instance_id, port, label, var_type, unit, value, min, max, steps, hw_type, hw_id, actuator_type, actuator_id, n_controllers, index, *options):
		print("control_add command")
		callback(True)

	def control_clean(self, callback, hw_type, hw_id, actuator_type, actuator_id):
		print("control_clean command")
		callback(True)

	@gen.coroutine
	def error_run_callback(self, result):
		if result == True:
			yield self.stream.write(b'resp 0\0')
		else:
			print("error_run_callback: " + str(result))
			yield self.stream.write(b'resp -1\0')
			#raise ProtocolError("error_run_callback: %s" % (result))
		return

	@gen.coroutine
	def socketService(self,data):
		if data:
			print(">socketService read: ", data)
			p = RpiProtocol(data.decode('utf-8'))
			if not p.is_resp():
				p.run_cmd(self.error_run_callback)
		self.stream.read_until(b'\0', callback=self.socketService)
		return

	@gen.coroutine
	def setup(self):
		self.stream = yield TCPClient().connect("localhost", PORT)
		self.socketService(None)
		return

	@gen.coroutine
	def socket_write(self, str):
		print("> send: %s" % str )
		yield self.stream.write(str)
		return

	def set_pedalboard(self, bank_id, pedalboard_id):
		self.socket_write("pedalboard {0} {0}\0".format(bank_id, pedalboard_id).encode('ascii'));
		return


class RotaryEncoderShell(object):
	def __init__(self, model):
		self.model = model
		self.consolein = PipeIOStream(sys.stdin.fileno())
		self.consoleout = PipeIOStream(sys.stdout.fileno())
		self.setup()
		return

#        "banks": [],
#        "pedalboards": [int],
#        "pedalboard": [int, str],
#        "hw_con": [int, int],
#        "hw_dis": [int, int],
#        "control_set": [int, str, float],
#        "control_get": [int, str],
#        "control_next": [int, int, int, int],
#        "tuner": [str],
#        "tuner_input": [int],
#        "pedalboard_save": [],
#        "pedalboard_reset": [],
#        "jack_cpu_load": [],

#{(0, 0, 2, 1): '/hmi/knob2',
# (0, 0, 2, 3): '/hmi/knob4',
# (0, 0, 1, 3): '/hmi/footswitch4',
# (0, 0, 1, 1): '/hmi/footswitch2',
# (0, 0, 2, 0): '/hmi/knob1',
# (0, 0, 2, 2): '/hmi/knob3',
# (0, 0, 1, 2): '/hmi/footswitch3',
# (0, 0, 1, 0): '/hmi/footswitch1'}

	@gen.coroutine
	def readNext(self, data):
		global ssocket
		if data:
			print (">Read on console: ", data)
			if data.startswith(b"next"):
				#data = data[:-1] +  b"\0"
				#print (">>send banks")
				#ssocket.stream.write(b"banks\0");
				#print (">>send pedalboards 0")
				#ssocket.stream.write(b"pedalboards 0\0");
				#print (">>send pedalboard 0 2")
				#ssocket.stream.write(b"pedalboard 0 2\0");
				model.change_pedalboards(1)
				# control_next 0 0 2 0
				#ssocket.stream.write(b"jack_cpu_load\0");
			#	ssocket.stream.write(b"tuner off\0");
			#	ssocket.stream.write(b"tuner on\0"); control_get 0 gain over
				#print (">>send control_get 0 \":bypass\"")
				#ssocket.stream.write(b"control_get 0 \":bypass\"\0");
			#	ssocket.stream.write(b"control_get 9995 :presets\0");
			elif data.startswith(b"prev"):
				model.change_pedalboards(-1)
			else:
				data = data[:-1] +  b"\0"
				ssocket.stream.write(data);

		self.consolein.read_until(b'\n', self.readNext)

	def setup(self):
		self.readNext(None)
		return;


if __name__ == "__main__":
	global lcd, encoder, main_loop, rshell, ssocket
	lcd = FakeLCD()
	model = PedalModel(lcd)
	rshell = RotaryEncoderShell(model)
	encoder = FakeRotaryEncoder(0, 0, 0, rotaryEncoderCallback)
	lcd.clear()
	lcd.message("Welcome to --->\n  pedalpII")
	ssocket = SocketService(model)
	model.controller = ssocket
	#sleep(3)
	try:
		main_loop = tornado.ioloop.IOLoop.instance()
		print("Tornado Server started")
		main_loop.start()
	except:
		print("Exception triggered - Tornado Server stopped.")
		GPIO.cleanup()
		lcd.clear()
		lcd.destroy()
