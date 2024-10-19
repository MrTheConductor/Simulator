import argparse
import serial
import struct
from enum import Enum
from dataclasses import dataclass
import numpy as np
import tkinter as tk
from tkinter import ttk
import threading
import random

parser = argparse.ArgumentParser()
parser.add_argument("-p", "--port", help="set serial port to use",
                    type=str, default="COM8")
args = parser.parse_args()

def uint8_to_bytes(data):
    return data.to_bytes(1, byteorder='big')

def float16_to_bytes(data, base=10):
    fixed16 = int(data * base);
    return fixed16.to_bytes(2, byteorder='big', signed=True)

def float32_to_bytes(data, base=1):
    fixed32 = int(data * base);
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

class BatteryVoltageControl:
    def __init__(self, master):
        self.master = master
        self.min_voltage = tk.DoubleVar()
        self.max_voltage = tk.DoubleVar()
        self.voltage = tk.DoubleVar()

        self.min_spinbox = tk.Spinbox(master, from_=0.0, to=10.0, textvariable=self.min_voltage)
        self.min_spinbox.pack()

        self.max_spinbox = tk.Spinbox(master, from_=0.0, to=10.0, textvariable=self.max_voltage)
        self.max_spinbox.pack()

        self.scale = tk.Scale(master, from_=self.min_voltage.get(), to=self.max_voltage.get(), resolution=0.1, orient=tk.HORIZONTAL, variable=self.voltage)
        self.scale.pack()

        self.update_scale()

        self.min_spinbox.config(command=self.update_scale)
        self.max_spinbox.config(command=self.update_scale)

    def update_scale(self):
        self.scale.config(from_=self.min_voltage.get(), to=self.max_voltage.get())

class GUI(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("VESC Simulator")

        self.grid_columnconfigure(1, minsize=200)

        self.label_temp_fet = tk.Label(self, text="temp_fet")
        self.label_temp_motor = tk.Label(self, text="temp_motor")
        self.label_avg_motor_current = tk.Label(self, text="avg_motor_current")
        self.label_avg_input_current = tk.Label(self, text="avg_input_current")
        self.label_avg_id = tk.Label(self, text="avg_id")
        self.label_avg_iq = tk.Label(self, text="avg_iq")
        self.label_duty_cycle_now = tk.Label(self, text="duty_cycle_now")
        self.label_voltage_filtered = tk.Label(self, text="voltage_filtered")
        self.label_amp_hours = tk.Label(self, text="amp_hours")
        self.label_amp_hours_charged = tk.Label(self, text="amp_hours_charged")
        self.label_watt_hours = tk.Label(self, text="watt_hours")
        self.label_watt_hours_charged = tk.Label(self, text="watt_hours_charged")
        self.label_tachometer = tk.Label(self, text="tachometer")
        self.label_tachometer_abs = tk.Label(self, text="tachometer_abs")
        self.label_fault = tk.Label(self, text="fault")
        self.label_rpm = tk.Label(self, text="rpm")

        self.label_temp_fet.grid(row=0, column=0)
        self.label_temp_motor.grid(row=1, column=0)
        self.label_avg_motor_current.grid(row=2, column=0)
        self.label_avg_input_current.grid(row=3, column=0)
        self.label_avg_id.grid(row=4, column=0)  
        self.label_avg_iq.grid(row=5, column=0)
        self.label_duty_cycle_now.grid(row=6, column=0) 
        self.label_voltage_filtered.grid(row=7, column=0)   
        self.label_amp_hours.grid(row=8, column=0)
        self.label_amp_hours_charged.grid(row=9, column=0)
        self.label_watt_hours.grid(row=10, column=0)
        self.label_watt_hours_charged.grid(row=11, column=0)
        self.label_tachometer.grid(row=12, column=0)
        self.label_tachometer_abs.grid(row=13, column=0)
        self.label_fault.grid(row=14, column=0)
        self.label_rpm.grid(row=15, column=0)

        # Battery settings
        voltage_filtered_slider = tk.Scale(self, from_=0, to=100, orient=tk.HORIZONTAL, label="Battery Voltage", resolution=0.1, command=lambda value: setattr(values, "voltage_filtered", float(value)))
        voltage_filtered_slider.set(60.0)  # initial value
        voltage_filtered_slider.grid(row=7, column=1, sticky="ew")

        voltage_filtered_min = tk.Spinbox(self, from_=0, to=100, increment=0.1)
        voltage_filtered_min.grid(row=7, column=2, sticky="ew")

        duty_cycle_slider = tk.Scale(self, from_=0, to=1, orient=tk.HORIZONTAL, label="Duty Cycle", resolution=0.01, command=lambda value: setattr(values, "duty_cycle_now", float(value)))
        duty_cycle_slider.set(0.0)  # initial value
        duty_cycle_slider.grid(row=6, column=1, sticky="ew")

        avg_input_current_slider = tk.Scale(self, from_=0, to=1, orient=tk.HORIZONTAL, label="Average Input Current", resolution=0.01, command=lambda value: setattr(values, "avg_input_current", float(value)))
        avg_input_current_slider.set(0.0)  # initial value
        avg_input_current_slider.grid(row=3, column=1, sticky="ew")

        rpm_slider = tk.Scale(self, from_=-8000, to=8000, orient=tk.HORIZONTAL, label="RPM", resolution=1, command=lambda value: setattr(values, "rpm", float(value)))
        rpm_slider.set(0)  # initial value
        rpm_slider.grid(row=15, column=1, sticky="ew")

run_thread = True

def serial_port_main_loop():
    global run_thread
    with serial.Serial(args.port, 115200) as ser:
        while run_thread:
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
                    if random.random() < 0.1:
                        crc = 0xdead 
                    else:
                        crc = crc16(payload)
                    payload += crc.to_bytes(2, byteorder='big')
                    ser.write(b'\x02')
                    ser.write(payload_length.to_bytes(1, byteorder='big'))
                    ser.write(payload)
                    ser.write(b'\x03')
                else:
                    print("Unknown frame received")
            else:
                print('Invalid frame received')

serial_thread = threading.Thread(target=serial_port_main_loop)
# serial_thread.start()

gui = GUI()
# control = BatteryVoltageControl(gui)
gui.mainloop()

# Check if the serial thread is still running
if serial_thread.is_alive():
    run_thread = False
    # Wait for the thread to finish
    serial_thread.join()