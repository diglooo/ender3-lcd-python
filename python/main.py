#!/usr/bin/env python3
import argparse
import signal
import socket
import threading
import time
import psutil
import serial
from PIL import Image, ImageDraw, ImageFont

from framebuffer import FrameBuffer

SYNC_BYTES = b"\xA5\x5A"
RETRY_INTERVAL = 5

def open_serial(port, baudrate, timeout=1):
    while True:
        try:
            ser = serial.Serial(port, baudrate, timeout=timeout)
            ser.reset_input_buffer()
            ser.reset_output_buffer()
            print(f"Connected to {port}")
            return ser
        except serial.SerialException as e:
            print(f"Cannot open {port}: {e}. Retrying in {RETRY_INTERVAL}s...")
            time.sleep(RETRY_INTERVAL)


def send_frame(ser, frame_bytes):
    ser.write(SYNC_BYTES)
    ser.write(frame_bytes)
    ser.flush()


def get_ip():
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("8.8.8.8", 80))
            return s.getsockname()[0]
    except Exception:
        return "N/A"


def has_internet(host="8.8.8.8", port=53, timeout=2):
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def render(frame):
    cpu = psutil.cpu_percent(interval=None)
    mem = psutil.virtual_memory()
    uptime_s = int(time.time() - psutil.boot_time())
    uptime = f"{uptime_s // 3600}h{(uptime_s % 3600) // 60:02d}m"
    ip = get_ip()
    internet = "UP" if has_internet() else "DOWN"
    ram_used = mem.used // (1024 * 1024)
    ram_total = mem.total // (1024 * 1024)
    disk = psutil.disk_usage("/").percent

    #20 colums, 6 lines
    titles = [
        "IP",
        "Internet",
        "CPU",
        "RAM",
        "Disk /",
        "Uptime"
    ]

    #20 colums, 6 lines
    values = [
        (ip).rjust(21),
        internet.rjust(21),
        (f"{cpu:.1f}%").rjust(21),
        (f"{ram_used}/{ram_total}MB").rjust(21),
        (f"{disk:.1f}%").rjust(21),
        (uptime).rjust(21),
    ]


    frame.clear()
    image = Image.new("1", (frame.width, frame.height), 1)
    draw = ImageDraw.Draw(image)
    font = ImageFont.truetype("/home/diglo/.local/share/fonts/CozetteVector.ttf", 12, encoding="unic")
    for i, line in enumerate(titles):
        draw.text((0, i * 10), line, font=font, fill=0)
    for i, line in enumerate(values):
        draw.text((0, i * 10), line, font=font, fill=0)
    frame.from_pil_image(image)


def main():
    parser = argparse.ArgumentParser(description="Draw and stream a 128x64x1bpp framebuffer over serial.")
    parser.add_argument("--port", required=True, help="Serial port")
    args = parser.parse_args()

    frame = FrameBuffer()
    ser = open_serial(args.port, 115200)

    def tick():
        nonlocal ser
        try:
            render(frame)
            send_frame(ser, frame.as_bytes())
        except serial.SerialException as e:
            print(f"Serial error: {e}. Reconnecting...")
            try:
                ser.close()
            except Exception:
                pass
            ser = open_serial(args.port, 115200)
        t = threading.Timer(1.0, tick)
        t.daemon = True
        t.start()

    stop = threading.Event()

    def shutdown(*_):
        print("Shutting down...")
        stop.set()

    signal.signal(signal.SIGTERM, shutdown)
    signal.signal(signal.SIGINT, shutdown)

    tick()
    stop.wait()
    ser.close()

if __name__ == "__main__":
    main()
