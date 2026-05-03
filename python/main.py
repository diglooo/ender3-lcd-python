#!/usr/bin/env python3
import argparse
import signal
import socket
import subprocess
import threading
import time
import psutil
import serial
from PIL import Image, ImageDraw, ImageFont
from framebuffer import FrameBuffer
from historybuffer import HistoryBuffer
from UPSC import run_upsc, UPSC
from apc_monitor import APCMonitor

SYNC_BYTES = b"\xA5\x5A"
RETRY_INTERVAL = 5

hb_cpu_usage = HistoryBuffer(48)
hb_cpu_temperature = HistoryBuffer(48)
frames=0
cpu_a=0
cpu_temp_a=0
apc_monitor = None

def render_plot(history, height):
    width=history.get_maxlen()
    samples=history.get_history()

    if not samples:
        return Image.new('1', (width, height), 1)
    
    # Reverse history so newest is at x=0
    reversed_history = list(reversed(samples))
    
    # If more than width, take the newest width samples
    if len(reversed_history) > width:
        plot_data = reversed_history[:width]
    else:
        plot_data = reversed_history
    
    img = Image.new('1', (width, height), 1)
    draw = ImageDraw.Draw(img)
    
    if not plot_data:
        return img
    
    min_val = 0
    max_val = 100

    points = []
    for x, val in enumerate(plot_data):
        y = height - 1 - int((val - min_val) / (max_val - min_val) * (height - 1))
        points.append((x, y))
    
    if len(points) > 1:
        draw.line(points, fill=0)
    
    return img

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

def get_cpu_temperature():
    try:
        result = subprocess.run(['sensors'], capture_output=True, text=True, timeout=5)
        lines = result.stdout.split('\n')
        for line in lines:
            if 'Package id 0:' in line:
                parts = line.split()
                if len(parts) >= 3:
                    temp_str = parts[3]
                    if temp_str.endswith('°C'):
                        return int(float(temp_str[:-2]))
    except Exception:
        return None

def render(frame):
    global hb_cpu_usage
    global hb_cpu_temperature
    global frames, cpu_temp_a, cpu_a
    global apc_monitor

    # Get UPS data from APCMonitor
    upsstr = "--"
    if apc_monitor:
        status = apc_monitor.get('STATUS', "UNKNOWN")
        loadpct = apc_monitor.get('LOADPCT', 0)
        timeleft = apc_monitor.get('TIMELEFT', 0)
        #print(f"APC STATUS: {status}, TIMELEFT: {timeleft}, LOADPCT: {loadpct}")
        if status and timeleft:
            loadpct = loadpct.split()[0] 
            timeleft = timeleft.split()[0]
            upsstr = f"{status} {int(float(timeleft))}min {int(float(loadpct))}W"
        else:
            upsstr = "UPS Error"

    cpu = psutil.cpu_percent(interval=None)
    
    cpu_temp=get_cpu_temperature()
    
    mem = psutil.virtual_memory()
    
    uptime_s = int(time.time() - psutil.boot_time())
    days = uptime_s // 86400
    hours = (uptime_s % 86400) // 3600
    minutes = (uptime_s % 3600) // 60
    uptime = f"{days}d{hours}h{minutes}m"

    ip = get_ip()
    internet = "UP" if has_internet() else "DOWN"
    ram_used = mem.used / (1024 * 1024 * 1024)    
    ram_total = mem.total / (1024 * 1024 *1024)    
    nvme_usage = psutil.disk_usage("/").percent    
    hdd_usage = psutil.disk_usage("/mnt/satadisk").percent
    
    #20 colums, 6 lines
    titles = [
        "",
        "CPU",
        "RAM",
        "SSD",
        "HDD",
        "UP"
    ]

    #20 colums, 6 lines
    space_from_left=13
    values = [
        (upsstr),
        (f"{cpu_temp}°C/{int(cpu)}%").rjust(space_from_left),
        (f"{ram_used:.1f}/{ram_total:.1f}GB").rjust(space_from_left),
        (f"{nvme_usage:.1f}%").rjust(space_from_left),
        (f"{hdd_usage:.1f}%").rjust(space_from_left),
        (uptime).rjust(space_from_left),
    ]


    frame.clear()
    lcd_image = Image.new("1", (frame.width, frame.height), 1)

    #draw plots
    cpu_a += cpu/10
    cpu_temp_a += cpu_temp/10
    frames += 1
    if (frames%10)==0:
        hb_cpu_usage.add_sample(cpu_a)
        hb_cpu_temperature.add_sample(cpu_temp_a)
        cpu_a=0
        cpu_temp_a=0
        frames=0
    img_cpu_plot_img=render_plot(hb_cpu_usage, height=20)
    img_temp_plot_img=render_plot(hb_cpu_temperature, height=20)
    lcd_image.paste(img_cpu_plot_img, (128-48, 0))
    lcd_image.paste(img_temp_plot_img, (128-48, 30))

    draw = ImageDraw.Draw(lcd_image)
    font = ImageFont.truetype("CozetteVector.ttf", 12, encoding="unic")
    for i, line in enumerate(titles):
        draw.text((0, i * 10), line, font=font, fill=0)
    for i, line in enumerate(values):
        draw.text((0, i * 10), line, font=font, fill=0)


    frame.from_pil_image(lcd_image)

def main():
    global apc_monitor
    parser = argparse.ArgumentParser(description="Draw and stream a 128x64x1bpp framebuffer over serial.")
    parser.add_argument("--port", required=True, help="Serial port")
    args = parser.parse_args()

    frame = FrameBuffer()
    ser = open_serial(args.port, 115200)
    
    # Start APC Monitor
    apc_monitor = APCMonitor(interval=10)
    apc_monitor.start()

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
    
    # Clean up
    apc_monitor.stop()
    ser.close()

if __name__ == "__main__":
    main()
