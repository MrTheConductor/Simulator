import argparse
import time
import serial
import struct
from enum import Enum
from dataclasses import dataclass
import numpy as np
import tkinter as tk
from tkinter import ttk
import threading
import random
import sys

parser = argparse.ArgumentParser()
parser.add_argument("-p", "--port", help="set serial port to use",
                    type=str, default="COM8")
parser.add_argument("-f", "--fuzz", help="enable fuzzing of the custom app commands",
                    action="store_true", default=False)
args = parser.parse_args()

def uint8_to_bytes(data):
    return data.to_bytes(1, byteorder='big')

def float8_to_bytes(data, base=10):
    fixed8 = int(data * base)
    return fixed8.to_bytes(1, byteorder='big', signed=True)

def float16_to_bytes(data, base=10):
    fixed16 = int(data * base)
    return fixed16.to_bytes(2, byteorder='big', signed=True)

def float32_to_bytes(data, base=1):
    fixed32 = int(data * base)
    return fixed32.to_bytes(4, byteorder='big', signed=True)

@dataclass
class COMM_GET_VALUES:
    id: int 
    temp_fet: float 
    temp_motor: float
    avg_motor_current: float
    avg_input_current: float
    avg_id: float 
    avg_iq: float 
    duty_cycle_now: float 
    rpm: float 
    voltage_filtered: float 
    amp_hours: float 
    amp_hours_charged: float 
    watt_hours: float 
    watt_hours_charged: float 
    tachometer: float
    tachometer_abs: float 
    fault: int

    def to_bytearray(self) -> bytearray:
        # Define the struct format for packing data
        format_str = '1s2s2s4s4s4s4s2s4s2s4s4s4s4s4s4s1s'

        # Pack the data into a binary format
        data = struct.pack(
            format_str,
            uint8_to_bytes(self.id),
            float16_to_bytes(self.temp_fet),
            float16_to_bytes(self.temp_motor),
            float32_to_bytes(self.avg_motor_current),
            float32_to_bytes(self.avg_input_current, 100),
            float32_to_bytes(self.avg_id),
            float32_to_bytes(self.avg_iq),
            float16_to_bytes(self.duty_cycle_now, 1000),
            float32_to_bytes(self.rpm),
            float16_to_bytes(self.voltage_filtered),
            float32_to_bytes(self.amp_hours),
            float32_to_bytes(self.amp_hours_charged),
            float32_to_bytes(self.watt_hours),
            float32_to_bytes(self.watt_hours_charged),
            float32_to_bytes(self.tachometer),
            float32_to_bytes(self.tachometer_abs),
            uint8_to_bytes(self.id)
        )
        return bytearray(data)

@dataclass
class COMM_CUSTOM_APP_DATA:
    id: int
    floatpkg: int
    floatcmd: int
    state: int
    fault: int
    pitch_or_duty_cycle: int
    rpm: float
    avgInputCurrent: float
    inpVoltage: float
    headlightBrightness: int
    headlightIdleBrightness: int
    statusbarBrightness: int

    def to_bytearray(self) -> bytearray:
        # Define the struct format for packing data
        format_str = '1s1s1s1s1s1s2s2s2s1s1s1s'

        # Pack the data into a binary format
        data = struct.pack(
            format_str,
            uint8_to_bytes(self.id),
            uint8_to_bytes(self.floatpkg),
            uint8_to_bytes(self.floatcmd),
            uint8_to_bytes(self.state),
            uint8_to_bytes(self.fault),
            float8_to_bytes(self.pitch_or_duty_cycle, 100),
            float16_to_bytes(self.rpm),
            float16_to_bytes(self.avgInputCurrent, 100),
            float16_to_bytes(self.inpVoltage, 10),
            uint8_to_bytes(self.headlightBrightness),
            uint8_to_bytes(self.headlightIdleBrightness),
            uint8_to_bytes(self.statusbarBrightness)
        )
        return bytearray(data)

# CRC Table
crc16_tab = [
    0x0000, 0x1021, 0x2042, 0x3063, 0x4084, 0x50a5, 0x60c6, 0x70e7, 0x8108, 0x9129, 0xa14a, 0xb16b, 0xc18c, 0xd1ad,
    0xe1ce, 0xf1ef, 0x1231, 0x0210, 0x3273, 0x2252, 0x52b5, 0x4294, 0x72f7, 0x62d6, 0x9339, 0x8318, 0xb37b, 0xa35a,
    0xd3bd, 0xc39c, 0xf3ff, 0xe3de, 0x2462, 0x3443, 0x0420, 0x1401, 0x64e6, 0x74c7, 0x44a4, 0x5485, 0xa56a, 0xb54b,
    0x8528, 0x9509, 0xe5ee, 0xf5cf, 0xc5ac, 0xd58d, 0x3653, 0x2672, 0x1611, 0x0630, 0x76d7, 0x66f6, 0x5695, 0x46b4,
    0xb75b, 0xa77a, 0x9719, 0x8738, 0xf7df, 0xe7fe, 0xd79d, 0xc7bc, 0x48c4, 0x58e5, 0x6886, 0x78a7, 0x0840, 0x1861,
    0x2802, 0x3823, 0xc9cc, 0xd9ed, 0xe98e, 0xf9af, 0x8948, 0x9969, 0xa90a, 0xb92b, 0x5af5, 0x4ad4, 0x7ab7, 0x6a96,
    0x1a71, 0x0a50, 0x3a33, 0x2a12, 0xdbfd, 0xcbdc, 0xfbbf, 0xeb9e, 0x9b79, 0x8b58, 0xbb3b, 0xab1a, 0x6ca6, 0x7c87,
    0x4ce4, 0x5cc5, 0x2c22, 0x3c03, 0x0c60, 0x1c41, 0xedae, 0xfd8f, 0xcdec, 0xddcd, 0xad2a, 0xbd0b, 0x8d68, 0x9d49,
    0x7e97, 0x6eb6, 0x5ed5, 0x4ef4, 0x3e13, 0x2e32, 0x1e51, 0x0e70, 0xff9f, 0xefbe, 0xdfdd, 0xcffc, 0xbf1b, 0xaf3a,
    0x9f59, 0x8f78, 0x9188, 0x81a9, 0xb1ca, 0xa1eb, 0xd10c, 0xc12d, 0xf14e, 0xe16f, 0x1080, 0x00a1, 0x30c2, 0x20e3,
    0x5004, 0x4025, 0x7046, 0x6067, 0x83b9, 0x9398, 0xa3fb, 0xb3da, 0xc33d, 0xd31c, 0xe37f, 0xf35e, 0x02b1, 0x1290,
    0x22f3, 0x32d2, 0x4235, 0x5214, 0x6277, 0x7256, 0xb5ea, 0xa5cb, 0x95a8, 0x8589, 0xf56e, 0xe54f, 0xd52c, 0xc50d,
    0x34e2, 0x24c3, 0x14a0, 0x0481, 0x7466, 0x6447, 0x5424, 0x4405, 0xa7db, 0xb7fa, 0x8799, 0x97b8, 0xe75f, 0xf77e,
    0xc71d, 0xd73c, 0x26d3, 0x36f2, 0x0691, 0x16b0, 0x6657, 0x7676, 0x4615, 0x5634, 0xd94c, 0xc96d, 0xf90e, 0xe92f,
    0x99c8, 0x89e9, 0xb98a, 0xa9ab, 0x5844, 0x4865, 0x7806, 0x6827, 0x18c0, 0x08e1, 0x3882, 0x28a3, 0xcb7d, 0xdb5c,
    0xeb3f, 0xfb1e, 0x8bf9, 0x9bd8, 0xabbb, 0xbb9a, 0x4a75, 0x5a54, 0x6a37, 0x7a16, 0x0af1, 0x1ad0, 0x2ab3, 0x3a92,
    0xfd2e, 0xed0f, 0xdd6c, 0xcd4d, 0xbdaa, 0xad8b, 0x9de8, 0x8dc9, 0x7c26, 0x6c07, 0x5c64, 0x4c45, 0x3ca2, 0x2c83,
    0x1ce0, 0x0cc1, 0xef1f, 0xff3e, 0xcf5d, 0xdf7c, 0xaf9b, 0xbfba, 0x8fd9, 0x9ff8, 0x6e17, 0x7e36, 0x4e55, 0x5e74,
    0x2e93, 0x3eb2, 0x0ed1, 0x1ef0
]

def crc16(data):
    cksum = 0
    for byte in data:
        cksum = crc16_tab[((cksum >> 8) ^ byte) & 0xFF] ^ (cksum << 8)
    return cksum & 0xFFFF  # Ensure it stays within 16 bits

def parse_frame(data):
    if len(data) < 6:
        return None  # invalid frame length
    if data[0] != 0x02:
        return None  # invalid start byte
    if data[-1] != 0x03:
        return None  # invalid end byte
    length = data[1]
    if len(data) != length + 5:
        return None  # invalid frame length
    payload = data[2:-3]
    crc = struct.unpack('>H', data[-3:-1])[0]
    calculated_crc = crc16(payload)
    if crc != calculated_crc:
        print("Invalid CRC16: recieved 0x{:04x}, calculated 0x{:04x}".format(crc, calculated_crc))
        return None  # invalid CRC16
    return payload

values = COMM_GET_VALUES(
    id=0x04,
    temp_fet=0.0,
    temp_motor=0.0,
    avg_motor_current=0.0,
    avg_input_current=0.0,
    avg_id=0.0,
    avg_iq=0.0,
    duty_cycle_now=0.0,
    rpm=0.0,
    voltage_filtered=0.0,
    amp_hours=0.0,
    amp_hours_charged=0.0,
    watt_hours=0.0,
    watt_hours_charged=0.0,
    tachometer=0.0,
    tachometer_abs=0.0,
    fault=0
)

class RunState(Enum):
    STATE_DISABLED = 0
    STATE_STARTUP = 1
    STATE_READY = 2
    STATE_RUNNING = 3

lcm_poll_response = COMM_CUSTOM_APP_DATA(
    id = 0x24,
    floatpkg= 0x65,
    floatcmd = 0x18,
    state = 3,
    fault = 0, 
    pitch_or_duty_cycle = 0, 
    rpm = 0.0,
    avgInputCurrent = 0.0,
    inpVoltage = 0.0,
    headlightBrightness = 100,
    headlightIdleBrightness = 100,
    statusbarBrightness = 100 
)

class BatteryVoltageControl:
    def __init__(self, master):
        self.master = master
        # Initial values - approximate for 15S battery
        self.min_voltage = tk.DoubleVar(value=30.0)
        self.max_voltage = tk.DoubleVar(value=70.0)
        self.voltage = tk.DoubleVar(value=60.0)
        self.enable_tick = tk.BooleanVar(value=False)
        self.tick_up = False

        self.label_frame = tk.LabelFrame(master, text="Battery Voltage Control")
        self.label_frame.pack(padx=10, pady=10, fill=tk.X, expand=True)

        self.min_label = tk.Label(self.label_frame, text="Minimum Voltage:")
        self.min_label.grid(row=0, column=0, padx=5, pady=5)
        self.min_spinbox = tk.Spinbox(self.label_frame, from_=0.0, to=100.0, increment=0.1, textvariable=self.min_voltage)
        self.min_spinbox.grid(row=0, column=1, padx=5, pady=5)
        self.min_tooltip = tk.Label(self.label_frame, text="Minimum voltage threshold")
        self.min_tooltip.grid(row=0, column=2, padx=5, pady=5)

        self.max_label = tk.Label(self.label_frame, text="Maximum Voltage:")
        self.max_label.grid(row=1, column=0, padx=5, pady=5)
        self.max_spinbox = tk.Spinbox(self.label_frame, from_=0.0, to=200.0, increment=0.1, textvariable=self.max_voltage)
        self.max_spinbox.grid(row=1, column=1, padx=5, pady=5)
        self.max_tooltip = tk.Label(self.label_frame, text="Maximum voltage threshold")
        self.max_tooltip.grid(row=1, column=2, padx=5, pady=5)

        self.scale = tk.Scale(self.label_frame, from_=self.min_voltage.get(), to=self.max_voltage.get(), resolution=0.1, orient=tk.HORIZONTAL, variable=self.voltage)
        self.scale.grid(row=2, column=0, columnspan=3, padx=5, pady=5, sticky="ew")

        self.enable_tick_checkbox = tk.Checkbutton(self.label_frame, text="Enable", variable=self.enable_tick)
        self.enable_tick_checkbox.grid(row=3, column=0, columnspan=3, padx=5, pady=5)

        self.min_voltage.trace_add("write", self.update_scale)
        self.max_voltage.trace_add("write", self.update_scale)
        self.voltage.trace_add("write", self.update_voltage)

        self.update_voltage()

    def update_voltage(self, *args):
        values.voltage_filtered = self.voltage.get()
        lcm_poll_response.inpVoltage = self.voltage.get()

    def update_scale(self, *args):
        self.scale.config(from_=self.min_voltage.get(), to=self.max_voltage.get())
    
    def tick(self):
        if self.enable_tick.get():
            if self.tick_up:
                if self.voltage.get() < self.max_voltage.get():
                    self.voltage.set(self.voltage.get() + 0.01)
                else:
                    self.tick_up = False
            else:
                if self.voltage.get() > self.min_voltage.get():
                    self.voltage.set(self.voltage.get() - 0.01)
                else:
                    self.tick_up = True

class DutyCycleControl:
    def __init__(self, master):
        self.master = master
        self.duty_cycle = tk.DoubleVar()
        self.link_to_rpm = tk.BooleanVar(value=True)

        self.label_frame = tk.LabelFrame(master, text="Duty Cycle Control")
        self.label_frame.pack(padx=10, pady=10, fill=tk.X, expand=True)

        self.scale = tk.Scale(self.label_frame, from_=0.0, to=1.0, resolution=0.01, orient=tk.HORIZONTAL, variable=self.duty_cycle)
        self.scale.pack(padx=5, pady=5, fill=tk.X, expand=True)

        self.link_checkbox = tk.Checkbutton(self.label_frame, text="Link to RPM", variable=self.link_to_rpm)
        self.link_checkbox.pack(padx=5, pady=5)

        self.duty_cycle.trace_add("write", self.update_duty_cycle)
        self.update_duty_cycle()

    def update_duty_cycle(self, *args):
        values.duty_cycle_now = self.duty_cycle.get()
        lcm_poll_response.pitch_or_duty_cycle = self.duty_cycle.get()

    def update_duty_cycle_from_rpm(self, rpm):
        rpm = abs(rpm)
        if rpm >= 800:
            self.duty_cycle.set(1.0)
        else:
            self.duty_cycle.set(rpm / 800.0)

class InputCurrentControl:
    def __init__(self, master):
        self.master = master
        self.input_current = tk.DoubleVar()
        self.link_to_rpm = tk.BooleanVar(value=True)

        self.label_frame = tk.LabelFrame(master, text="Input Current Control")
        self.label_frame.pack(padx=10, pady=10, fill=tk.X, expand=True)

        self.scale = tk.Scale(self.label_frame, from_=0.0, to=1.0, resolution=0.01, orient=tk.HORIZONTAL, variable=self.input_current)
        self.scale.pack(padx=5, pady=5, fill=tk.X, expand=True)

        self.link_checkbox = tk.Checkbutton(self.label_frame, text="Link to RPM", variable=self.link_to_rpm)
        self.link_checkbox.pack(padx=5, pady=5)

        self.input_current.trace_add("write", self.update_input_current)
        self.update_input_current()

    def update_input_current(self, *args):
        values.avg_input_current = self.input_current.get()
        lcm_poll_response.avgInputCurrent = self.input_current.get()
    
    def update_input_current_from_rpm(self, rpm):
        rpm = abs(rpm)
        if rpm >= 200:
            self.input_current.set(1.0)
        else:
            self.input_current.set(rpm / 200.0)

class RPMControl:
    def __init__(self, master, duty_cycle_control, input_current_control):
        self.master = master
        self.duty_cycle_control = duty_cycle_control
        self.input_current_control = input_current_control
        self.enable_tick = tk.BooleanVar(value=False)
        self.tick_up = True

        self.min_rpm = tk.IntVar(value=-900)
        self.max_rpm = tk.IntVar(value=900)
        self.rpm = tk.IntVar(value=0)
        self.tire_circumference = tk.DoubleVar(value=32.75)
        self.speed_mph = tk.StringVar(value="0.0 mph")

        self.label_frame = tk.LabelFrame(master, text="RPM Control")
        self.label_frame.pack(padx=10, pady=10, fill=tk.X, expand=True)

        # Minimum RPM Spinbox
        self.min_label = tk.Label(self.label_frame, text="Min RPM")
        self.min_label.grid(row=0, column=0, padx=5, pady=5)
        self.min_spinbox = tk.Spinbox(self.label_frame, from_=-10000, to=10000, textvariable=self.min_rpm)
        self.min_spinbox.grid(row=0, column=1, padx=5, pady=5)

        # Maximum RPM Spinbox
        self.max_label =tk.Label(self.label_frame, text="Max RPM")
        self.max_label.grid(row=1, column=0, padx=5, pady=5)
        self.max_spinbox = tk.Spinbox(self.label_frame, from_=-10000, to=10000, textvariable=self.max_rpm)
        self.max_spinbox.grid(row=1, column=1, padx=5, pady=5)

        # RPM Scale
        self.rpm_scale = tk.Scale(self.label_frame, from_=self.min_rpm.get(), to=self.max_rpm.get(), orient=tk.HORIZONTAL, variable=self.rpm)
        self.rpm_scale.grid(row=2, column=0, columnspan=2, padx=5, pady=5, sticky="ew")

        # Speed MPH Label
        self.mph_label = tk.Label(self.label_frame, textvariable=self.speed_mph)
        self.mph_label.grid(row=2, column=3, padx=5, pady=5)

        # Tire Circumference Spinbox
        self.tire_circumference_label = tk.Label(self.label_frame, text="Tire Circumference (inches)")
        self.tire_circumference_label.grid(row=3, column=0, padx=5, pady=5)
        self.tire_circumference_spinbox = tk.Spinbox(self.label_frame, from_=0.0, to=100.0, increment=0.1, textvariable=self.tire_circumference)
        self.tire_circumference_spinbox.grid(row=3, column=1, padx=5, pady=5)

        # Update speed MPH label when RPM or tire circumference changes
        self.rpm.trace_add("write", self.update_speed_mph)
        self.tire_circumference.trace_add("write", self.update_speed_mph)
        self.update_speed_mph()

        self.enable_tick_checkbox = tk.Checkbutton(self.label_frame, text="Enable Tick", variable=self.enable_tick)
        self.enable_tick_checkbox.grid(row=4, column=0, columnspan=2, padx=5, pady=5)

    def update_speed_mph(self, *args):
        if self.input_current_control.link_to_rpm.get():
            self.input_current_control.update_input_current_from_rpm(self.rpm.get())

        if self.duty_cycle_control.link_to_rpm.get():
            self.duty_cycle_control.update_duty_cycle_from_rpm(self.rpm.get())

        values.rpm = self.rpm.get()
        lcm_poll_response.rpm = self.rpm.get()

        rpm = self.rpm.get()
        circumference = self.tire_circumference.get()
        speed_mph = (abs(rpm) * circumference ) / 1056   # convert RPM to MPH
        self.speed_mph.set(f"{speed_mph:.1f} mph")

        # Update RPM scale range when min or max RPM changes
        self.min_rpm.trace_add("write", self.update_rpm_scale)
        self.max_rpm.trace_add("write", self.update_rpm_scale)

    def update_rpm_scale(self, *args):
        self.rpm_scale.config(from_=self.min_rpm.get(), to=self.max_rpm.get())
    
    def tick(self):
        if self.enable_tick.get():
            if self.tick_up:
                if self.rpm.get() < self.max_rpm.get():
                    self.rpm.set(self.rpm.get() + 1)
                else:
                    self.tick_up = False
            else:
                if self.rpm.get() > self.min_rpm.get():
                    self.rpm.set(self.rpm.get() - 1)
                else:
                    self.tick_up = True

class FloatControl:
    def __init__(self, master):
        self.master = master
        self.enabled = tk.BooleanVar(value=True)
        self.headlight_brightness = tk.IntVar(value=80)
        self.headlight_idle_brightness = tk.IntVar(value=40)
        self.statusbar_brightness = tk.IntVar(value=40)

        self.label_frame = tk.LabelFrame(self.master, text="Float Control")
        self.label_frame.pack(padx=10, pady=10, fill=tk.X, expand=True)

        # Create checkbox to enable/disable settings
        tk.Checkbutton(self.label_frame, text="Enable", variable=self.enabled).grid(row=0, column=0, columnspan=2, padx=5, pady=5)

        # Create sliders
        tk.Label(self.label_frame, text="Headlight Brightness").grid(row=1, column=0, padx=5, pady=5)
        tk.Scale(self.label_frame, from_=0, to=100, orient=tk.HORIZONTAL, variable=self.headlight_brightness, command=self.update_headlight_brightness).grid(row=1, column=1, padx=5, pady=5, sticky=tk.EW)
        tk.Label(self.label_frame, text="Headlight Idle Brightness").grid(row=2, column=0, padx=5, pady=5)
        tk.Scale(self.label_frame, from_=0, to=100, orient=tk.HORIZONTAL, variable=self.headlight_idle_brightness, command=self.update_headlight_idle_brightness).grid(row=2, column=1, padx=5, pady=5, sticky=tk.EW)
        tk.Label(self.label_frame, text="Statusbar Brightness").grid(row=3, column=0, padx=5, pady=5)
        tk.Scale(self.label_frame, from_=0, to=100, orient=tk.HORIZONTAL, variable=self.statusbar_brightness, command=self.update_statusbar_brightness).grid(row=3, column=1, padx=5, pady=5, sticky=tk.EW)
        self.label_frame.grid_columnconfigure(1, weight=1)

    def update_headlight_brightness(self, value):
        lcm_poll_response.headlightBrightness = int(value)

    def update_headlight_idle_brightness(self, value):
        lcm_poll_response.headlightIdleBrightness = int(value)

    def update_statusbar_brightness(self, value):
        lcm_poll_response.statusbarBrightness = int(value)

stop_event = threading.Event()

def serial_port_main_loop():
    while not stop_event.is_set():
        try:
            with serial.Serial(args.port, 115200) as ser:
                while not stop_event.is_set():
                    data = bytearray()
                    while True:
                        byte = ser.read(1)
                        if byte == b'\x02':
                            data.append(byte[0])
                            break
                    while len(data) < 5:
                        byte = ser.read(1)
                        data.append(byte[0])
                    length = data[1]
                    while len(data) < length + 5:
                        byte = ser.read(1)
                        data.append(byte[0])
                    frame = parse_frame(data)
                    if frame:
                        if frame[0]==0x04:
                            payload = values.to_bytearray()
                            payload_length = len(payload)
                            crc = crc16(payload)
                            payload += crc.to_bytes(2, byteorder='big')
                            ser.write(b'\x02')
                            ser.write(payload_length.to_bytes(1, byteorder='big'))
                            ser.write(payload)
                            ser.write(b'\x03')
                        elif frame[0] == 0x24:
                            if frame[1] == 0x65:
                                if frame[2] == 0x18:
                                    payload = lcm_poll_response.to_bytearray()
                                    # Add payload fuzzer
                                    if args.fuzzer:
                                        for i in range(0, random.randint(0, 200)):
                                            payload.append(random.randint(0, 255))
                                    payload_length = len(payload)
                                    crc = crc16(payload)
                                    payload += crc.to_bytes(2, byteorder='big')
                                    ser.write(b'\x02')
                                    ser.write(payload_length.to_bytes(1, byteorder='big'))
                                    ser.write(payload)
                                    ser.write(b'\x03')
                                elif frame[2] == 0x1c:
                                    print("FLOAT_COMMAND_CHARGESTATE")
                                elif frame[2] == 0x63:
                                    print("FLOAT_COMMAND_LMC_DEBUG")
                                else:
                                    print("Unknown FLOAT_COMMAND")
                            else:
                                print("Unknown custom app")
                        else:
                            print("Unknown frame received")
                    else:
                        print('Invalid frame received')
        except Exception as e:
            print("Serial port error: ", e)
            time.sleep(5)

def ticking_loop():
    print("Ticking loop started")
    while not stop_event.is_set():
        time.sleep(0.01)
        rpm_control.tick()
        battery_control.tick()
    print("Ticking loop stopped")

serial_thread = threading.Thread(target=serial_port_main_loop)
serial_thread.start()

# gui = GUI()
root = tk.Tk()
root.title("VESC Simulator")
battery_control = BatteryVoltageControl(root)
duty_cycle_control = DutyCycleControl(root)
input_current_control = InputCurrentControl(root)
rpm_control = RPMControl(root, duty_cycle_control, input_current_control)
float_control = FloatControl(root)

tick_thread = threading.Thread(target=ticking_loop)
tick_thread.start()

root.mainloop()


# Check if the serial thread is still running
if serial_thread.is_alive() or tick_thread.is_alive():
    print("Waiting for threads to finish...")
    stop_event.set()
    serial_thread.join()
    tick_thread.join()
