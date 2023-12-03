import network
import omv
import rtsp
import sensor
import time
from mqtt import MQTTClient
from pyb import Pin, Timer

pin_ws  = Pin('PB9')                        # PB9   - TM4 CH4
pin_ds1 = Pin('PB8')                        # PB8   - TM4 CH3
pin_ps  = Pin('PA9')                        # PA9   - TM1 CH2
pin_ds2 = Pin('PA10')                       # PA10  - TM1 CH3
pin_l   = Pin(Pin.board.PG1, Pin.OUT_PP)    # PG1   - Lights

tim1 = Timer(1, freq = 250)
tim4 = Timer(4, freq = 250)

sleep_duration = 0.1 # [s]

ps_pwm  = tim1.channel(2, Timer.PWM, pin=pin_ps)
ws_pwm  = tim4.channel(4, Timer.PWM, pin=pin_ws)
ds1_pwm = tim4.channel(3, Timer.PWM, pin=pin_ds1)
ds2_pwm = tim1.channel(3, Timer.PWM, pin=pin_ds2)

## 20000 -> 2500us
## 12000 -> 1500us
## 4000  -> 500us

ps_pwm.pulse_width(0)
ws_pwm.pulse_width(0)
ds1_pwm.pulse_width(0)
ds2_pwm.pulse_width(0)

sensor.reset()

sensor.set_pixformat(sensor.RGB565)
sensor.set_framesize(sensor.QVGA)
omv.disable_fb(True)

# Setup Network Interface

network_if = network.WLAN(network.STA_IF)
network_if.active(True)
network_if.connect("****", "****")
while not network_if.isconnected():
    print("Trying to connect. Note this may take a while...")
    time.sleep_ms(1000)

client = MQTTClient("nicla_vision", '192.168.1.101', port=1883)
client.connect()

# Setup RTSP Server
server = rtsp.rtsp_server(network_if)
clock = time.clock()

def setup_callback(pathname, session):
    print('Opening "%s" in session %d' % (pathname, session))

def play_callback(pathname, session):
    clock.reset()
    clock.tick()
    print('Playing "%s" in session %d' % (pathname, session))

def pause_callback(pathname, session):  # VLC only pauses locally. This is never called.
    print('Pausing "%s" in session %d' % (pathname, session))

def teardown_callback(pathname, session):
    print('Closing "%s" in session %d' % (pathname, session))

server.register_setup_cb(setup_callback)
server.register_play_cb(play_callback)
server.register_pause_cb(pause_callback)
server.register_teardown_cb(teardown_callback)

#                                   Control logic
# ____________________________________________________________________________________________
# |    Command   |    Description    |               Action
# ____________________________________________________________________________________________
# |      0       |       Stop        |   Stop all PWM on motors
# |      1       |     Forward       |   ds1 to 4000, ds2 to 20000
# |      2       |     Backwards     |   ds1 to 20000, ds2 to 4000
# |      3       |    Wheels down    |   ps  to 4000
# |      4       |     Wheels up     |   ps  to 20000
# |      5       |        Up         |   ws  to 4000
# |      6       |       Down        |   ws  to 20000
# |      7       |    Stop Winch     |   ws  to 0
# |      8       |    Lights ON      |   pin_l.on()
# |      9       |    Lights OFF     |   pin_l.off()
# |      11      |       Left        |   ds1 to 4000, ds2 to 4000
# |      21      |      Right        |   ds1 to 20000, ds2 to 20000

def callback_mqtt(topic, msg):
    global command
    command = msg.decode('utf-8')
    print(topic, msg.decode('utf-8'))
    cmd = int(command[-1])

    if cmd == 0:
        print('Received command - STOP')
        ds1_pwm.pulse_width(0)
        ds2_pwm.pulse_width(0)
    elif cmd == 1:
        cmd2 = int(command[-2])
        if cmd2 == 1:
            print('Received command - LEFT')
            ds1_pwm.pulse_width(4000)
            time.sleep(sleep_duration)
            ds2_pwm.pulse_width(4000)
        elif cmd2 == 2:
            print('Received command - RIGHT')
            ds1_pwm.pulse_width(20000)
            time.sleep(sleep_duration)
            ds2_pwm.pulse_width(20000)
        else:
            print('Received command - FORWARD')
            ds1_pwm.pulse_width(20000)
            time.sleep(sleep_duration)
            ds2_pwm.pulse_width(4000)
    elif cmd == 2:
        print('Received command - BACKWARDS')
        ds1_pwm.pulse_width(4000)
        time.sleep(sleep_duration)
        ds2_pwm.pulse_width(20000)
    elif cmd == 3:
        print('Received command - WHEELS DOWN')
        ps_pwm.pulse_width(4000)
    elif cmd == 4:
        print('Received command - WHEELS UP')
        ps_pwm.pulse_width(20000)
    elif cmd == 5:
        print('Received command - WINCH UP')
        ws_pwm.pulse_width(4000)
    elif cmd == 6:
        print('Received command - WINCH DOWN')
        ws_pwm.pulse_width(20000)
    elif cmd == 7:
        print('Received command - WINCH STOP')
        ws_pwm.pulse_width(0)
    elif cmd == 8:
        print('Received command - LIGHTS ON')
        pin_l.on()
    elif cmd == 9:
        print('Received command - LIGHTS OFF')
        pin_l.off()
    else:
        print('ERROR')
        print('Unknown Command!!!!!')


# must set callback first
client.set_callback(callback_mqtt)
client.subscribe("nicla/test")

# Called each time a new frame is needed.
def image_callback(pathname, session):
    img = sensor.snapshot()
    # Markup image and/or do various things.
    #print(clock.fps())
    clock.tick()
    client.check_msg()
    return img

# Stream does not return. It will call `image_callback` when it needs to get an image object to send
# to the remote rtsp client connecting to the server.

server.stream(image_callback, quality=90)
