#Antes de realizar un cambio en el codigo consultar el manual para evitar errores o preguntar al programador del mismo

import machine
import utime
import math
import network
import socket
import json

SSID = "IGRIS 7897" 
PASSWORD = "19r8X20("

wlan = network.WLAN(network.STA_IF)
wlan.active(True)
wlan.active(False)  
utime.sleep(0.5)    
wlan.active(True)
wlan.connect(SSID, PASSWORD)

print("Conectando a WiFi...", end="")
while not wlan.isconnected():
    utime.sleep(0.5)
    print(".", end="")
print("\nConectado. IP del ESP32:", wlan.ifconfig()[0])

uart = machine.UART(2, baudrate=256000, tx=17, rx=16, bits=8, parity=None, stop=1)
HEADER = bytes([0xAA, 0xFF, 0x03, 0x00])
FRAME_LEN = 30

def decode_val(lo, hi):
    raw = (hi << 8) | lo
    if raw == 0: return 0
    val = raw & 0x7FFF
    return -val if (raw & 0x8000) else val

def read_frame():
    state = 0
    buf = bytearray(FRAME_LEN)
    idx = 0
    deadline = utime.ticks_ms() + 50  #
    
    while utime.ticks_diff(deadline, utime.ticks_ms()) > 0:
        if not uart.any():
            utime.sleep_ms(1)
            continue
        
        b = uart.read(1)[0]
        if state == 0:
            if b == 0xAA: state = 1
        elif state == 1: state = 2 if b == 0xFF else 0
        elif state == 2: state = 3 if b == 0x03 else 0
        elif state == 3:
            if b == 0x00:
                buf[0:4] = HEADER
                idx = 4
                state = 4
            else: state = 0
        elif state == 4:
            buf[idx] = b
            idx += 1
            if idx == FRAME_LEN:
                if buf[28] == 0x55 and buf[29] == 0xCC: return bytes(buf)
                state = 0; idx = 0
    return None

def parse_targets(frame):
    targets = []
    for i in range(3):
        base = 4 + i * 8
        x = decode_val(frame[base], frame[base + 1])
        y = - decode_val(frame[base + 2], frame[base + 3])
        speed = decode_val(frame[base + 4], frame[base + 5])
        res = (frame[base + 7] << 8) | frame[base + 6]
        if y != 0:
            targets.append({"id": i, "x": x, "y": y, "speed": speed, "res": res})
    return targets


s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
s.bind(('', 80))
s.listen(1)
s.setblocking(False) 

latest_data = []

print("\nRadar HLK-LD2450 operando. API sirviendo en el puerto 80.")

while True:
    frame = read_frame()
    if frame is not None:
        latest_data = parse_targets(frame)
    try:
        conn, addr = s.accept()
        req = conn.recv(1024)
        response = json.dumps(latest_data)
        headers = 'HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nAccess-Control-Allow-Origin: *\r\n\r\n'
        
        conn.send((headers + response).encode('utf-8'))
        conn.close()
    except OSError:
        pass 

    utime.sleep_ms(1)