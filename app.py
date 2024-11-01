# <-------- Waiscreen -------->

from decimal import Decimal

# <-------- If the screen too lag, edit these value -------->
# Image Quality: Value range (0.1 ~ 1), '1' is the default value
# Reduce the image quality to reduce screen lagging
IMG_QUALITY: Decimal = Decimal(1)
# Allow Auto Restart Server: Value (True / False), 'True' is the default value
# Attempt to restart the server to reduce screen lagging after 30 client alerts
ALLOW_AUTO_RESTART_SERVER: bool = True
# Allow Auto Reduce Image Quality: Value (True / False), 'True' is the default value
# Attempt to reduce the image quality to reduce screen lagging after 3 client alerts
ALLOW_AUTO_REDUCE_IMG_QUALITY: bool = True

from flask import Flask, render_template, url_for, request, redirect, copy_current_request_context
from flask_socketio import SocketIO, emit
import cv2
import base64
import numpy as np
from mss import mss
from PIL import Image
import ctypes
import socket
import os, sys

APP = Flask(__name__)
SOCKETIO = SocketIO(APP)
sct = mss()

monitors = sct.monitors

active_clients = []
client_alerts = []

highest_screen_top_pos = 0
lowest_screen_top_pos = 9999
fst_screen_left_pos = 0

# Check the arguments
if len(sys.argv) > 1 and '--monitor=' in sys.argv[1]:
    selected_monitor = sys.argv[1].split('=')[-1]
    if selected_monitor.isdigit() and int(selected_monitor) < len(monitors):
        selected_monitor = int(selected_monitor)
        IMG_QUALITY: Decimal = Decimal(1)
        print(f"[Server] Selected monitor {selected_monitor}")
    else:
        selected_monitor = None
else:
    selected_monitor = None

# Get all the monitors that are availabled in this computer
monitor_images_list = []
for idx, monitor in enumerate(monitors):
    sct_img = sct.grab(monitor)
    img = Image.frombytes('RGB', (sct_img.width, sct_img.height), sct_img.rgb)

    # Check the screen width and height
    if len(monitors) > 1:   
        if idx != 0:
            if monitor['top'] > highest_screen_top_pos:
                highest_screen_top_pos = monitor['top']
            if monitor['top'] < lowest_screen_top_pos:
                lowest_screen_top_pos = monitor['top']

            if monitor['left'] < -fst_screen_left_pos:
                fst_screen_left_pos = abs(monitor['left'])

    os.makedirs('./static/images/screens', exist_ok=True)
    img.save(f"./static/images/screens/screen-{idx}.jpg")
    monitor_images_list.append(f"images/screens/screen-{idx}.jpg")

@APP.route('/clientalert', methods=['POST'])
def client_alert():
    global selected_monitor, IMG_QUALITY
    # Get the alert status and message
    status: int = request.json.get('status')
    msg: str = request.json.get('msg')

    # Add the alert
    client_alerts.append({
        "status": status,
        "msg": msg
    })

    # Output the alert
    print(f"[Client Alert] <{status}> {msg}")

    # If the alerts more than 3 times
    if len(client_alerts) > 30 and ALLOW_AUTO_RESTART_SERVER:
        print("[Server] Received more than 30 client alerts, attempt to restart the server ...")
        client_alerts.clear()
        os.execl(sys.executable, sys.executable, *(sys.argv + [f'--monitor={selected_monitor}']))

    # If the alerts more than 3 times
    elif len(client_alerts) > 3 and ALLOW_AUTO_REDUCE_IMG_QUALITY:
        if IMG_QUALITY > Decimal(0.5):
            IMG_QUALITY -= Decimal(0.01)
            print(f"[Server] Received more than 3 client alerts, attempt to reduce the image quality (Image quality set to '{float(IMG_QUALITY)}') ...")

    return "Alert added"

@APP.route('/shutdown', methods = ['POST'])
def shutdown_server():
    # Check if the client is the host
    if socket.gethostbyname(socket.gethostname()) == request.remote_addr:
        print("[Server] Shutting down ...")
        sys.exit(0)

    return "Access denied!"

@APP.route('/restart', methods = ['POST'])
def restart_server():
    # Check if the client is the host
    if socket.gethostbyname(socket.gethostname()) == request.remote_addr:
        print("[Server] Restarting ...")
        os.execl(sys.executable, sys.executable, *(sys.argv + [f'--monitor={selected_monitor}']))

    return "Access denied!"

@APP.route('/monitors', methods=['GET', 'POST'])
def monitors_page():
    if socket.gethostbyname(socket.gethostname()) != request.remote_addr:
        return "Access denied!"

    global selected_monitor
    if request.method == 'POST':
        selected_monitor = int(request.form.get('monitor'))
        print(f"[Server] Selected monitor {selected_monitor}")
        return redirect('./')

    monitors_list: list = list(enumerate(monitor_images_list))
    if len(monitors_list) <= 2:
        monitors_list: list = [(1, monitors_list[0][1])]
    return render_template('monitors.html', monitors = monitors_list, is_multi_monitors = len(monitor_images_list) > 2)

@APP.route('/')
def index():
    if not (selected_monitor != None):
        if socket.gethostbyname(socket.gethostname()) != request.remote_addr:
            return "Please wait for the host to set up the monitors"
        else:
            return redirect('/monitors')

    return render_template('index.html', is_host = socket.gethostbyname(socket.gethostname()) == request.remote_addr, addr = request.remote_addr)

class Point(ctypes.Structure):
    _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]

class MouseCursor:
    def get_cursor_pos() -> tuple[int, int]:
        pt = Point()
        ctypes.windll.user32.GetCursorPos(ctypes.byref(pt))
        return pt.x, pt.y

def screen_capture(remote_addr: str, client_list: list):
    print(f"[Server] Readying to share the screen")

    # Initialize the 'mss'
    sct = mss()
    
    # Load cursor images
    cursor_white_image = Image.open('./static/images/cursor-white.png').resize((15, 15))
    cursor_black_image = Image.open('./static/images/cursor-black.png').resize((15, 15))
    cursor_highlight_green_image = Image.open('./static/images/cursor-highlight-green.png').resize((18, 18))
    cursor_highlight_blue_image = Image.open('./static/images/cursor-highlight-blue.png').resize((18, 18))

    while True:
        # Set the moniter
        monitor = sct.monitors[selected_monitor if selected_monitor else 0]

        # Capture the screen
        sct_img = sct.grab(monitor)
        img = Image.frombytes('RGB', (sct_img.width, sct_img.height), sct_img.rgb)

        # Get the mouse cursor position
        cursor_x, cursor_y = MouseCursor.get_cursor_pos()

        # Calculate the position where the cursor image should be pasted
        cursor_y += int(highest_screen_top_pos - lowest_screen_top_pos)
        cursor_x += fst_screen_left_pos

        cursor_overflow = False

        if selected_monitor != 0:
            cursor_x -= (monitor['left'] + fst_screen_left_pos)
            cursor_y -= (monitor['top'] + int(highest_screen_top_pos - lowest_screen_top_pos))

            if not (0 <= cursor_x <= img.width - 1 and 0 <= cursor_y <= img.height - 1):
                cursor_overflow = True

        cursor_position = (cursor_x, cursor_y)

        # Check if not the cursor overflow
        if not cursor_overflow:
            # Set current cursor
            if ctypes.windll.user32.GetAsyncKeyState(0x01) & 0x8000 != 0:
                current_cursor_image = cursor_highlight_green_image
            elif ctypes.windll.user32.GetAsyncKeyState(0x02) & 0x8000 != 0:
                current_cursor_image = cursor_highlight_blue_image
            elif (sum(img.getpixel((cursor_x, cursor_y))) // 3) > 130:
                current_cursor_image = cursor_black_image
            else:
                current_cursor_image = cursor_white_image

            # Paste the cursor image onto the screen capture
            # The third parameter is the mask
            img.paste(current_cursor_image, cursor_position, current_cursor_image)

        # Convert PIL image to OpenCV format
        img = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)

        # Set image quality
        if 0 < IMG_QUALITY < 1:
            img = cv2.resize(img, None, fx = float(IMG_QUALITY), fy = float(IMG_QUALITY))

        # Encode the image as JPEG
        _, buffer = cv2.imencode('.jpg', img)
        jpg_as_text = base64.b64encode(buffer).decode('utf-8')

        try:
            # Send the image to the client
            SOCKETIO.emit('stream', jpg_as_text)
            SOCKETIO.sleep(0.01)
        except:
            pass

        # Check if the client is not active
        if remote_addr not in active_clients:
            print(f"[Server] Client '{remote_addr}' disconnected from the 'screen_capture' socketio")
            print(f"[Server] Client list: {client_list}")
            break

@SOCKETIO.on('connect')
def handle_connect():
    @copy_current_request_context
    def add_client():
        active_clients.append(request.remote_addr)
        return request.remote_addr

    remote_addr: str = add_client()

    print(f"[Server] Client '{remote_addr}' connected")
    SOCKETIO.start_background_task(target=screen_capture, remote_addr=remote_addr, client_list=active_clients)

@SOCKETIO.on('disconnect')
def handle_disconnect():
    @copy_current_request_context
    def remove_client():
        active_clients.remove(request.remote_addr)
        return request.remote_addr

    remote_addr: str = remove_client()

    print(f"[Server] Client '{remote_addr}' disconnected")

if __name__ == '__main__':
    print(f"[Server Started] The server is hosted at 'http://{socket.gethostbyname(socket.gethostname())}'")
    print(f"[Server Started] Press 'Ctrl + C' to stop the server")
    SOCKETIO.run(APP, '0.0.0.0', 80)
