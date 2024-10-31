from flask import Flask, render_template, url_for, request, redirect
from flask_socketio import SocketIO, emit
import cv2
import base64
import numpy as np
from mss import mss
from PIL import Image, ImageDraw, ImageOps
import keyboard
import pymouse
import copy
import random

app = Flask(__name__)
socketio = SocketIO(app)

selected_monitors = 0

sct = mss()
monitors = copy.deepcopy(sct.monitors)
monitor_images_list = []
for idx, monitor in enumerate(sct.monitors):
    sct_img = sct.grab(monitor)
    img = Image.frombytes('RGB', (sct_img.width, sct_img.height), sct_img.rgb)
    img.save(f"./static/images/screens/screen-{idx}.jpg")
    monitor_images_list.append(f"images/screens/screen-{idx}.jpg")

@app.route('/monitors', methods=['GET', 'POST'])
def monitors_page():
    global selected_monitors
    if request.method == 'POST':
        selected_monitors = int(request.form.get('monitor'))
        return redirect('./')

    return render_template('monitors.html', monitors = enumerate(monitor_images_list))

@app.route('/')
def index():
    return render_template('index.html')

def capture_screen_with_cursor():
    # Load cursor images
    cursor_white_image = Image.open('./static/images/cursor-white.png').resize((15, 15))
    cursor_black_image = Image.open('./static/images/cursor-black.png').resize((15, 15))

    while True:
        # Set the moniter
        monitor = sct.monitors[selected_monitors]

        # Capture the screen
        sct_img = sct.grab(monitor)
        img = Image.frombytes('RGB', (sct_img.width, sct_img.height), sct_img.rgb)

        # Get the mouse cursor position
        cursor_x, cursor_y = pymouse.PyMouse().position()

        # Calculate the position where the cursor image should be pasted
        cursor_overflow = False
        if cursor_x >= img.width - 1:
            cursor_overflow = True
            cursor_x = 0
        if cursor_y >= img.height - 1:
            cursor_overflow = True
            cursor_y = 0
        cursor_position = (cursor_x, cursor_y)

        # Set current cursor
        if (sum(img.getpixel((cursor_x, cursor_y))) // 3) > 130:
            current_cursor_image = cursor_black_image
        else:
            current_cursor_image = cursor_white_image

        # Paste the cursor image onto the screen capture
        # The third parameter is the mask
        if not cursor_overflow:
            img.paste(current_cursor_image, cursor_position, current_cursor_image)

        # Convert PIL image to OpenCV format
        img = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)

        # Encode the image as JPEG
        _, buffer = cv2.imencode('.jpg', img)
        jpg_as_text = base64.b64encode(buffer).decode('utf-8')

        # Send the image to the client
        socketio.emit('stream', jpg_as_text)
        socketio.sleep(0.1)

@socketio.on('connect')
def handle_connect():
    socketio.start_background_task(target=capture_screen_with_cursor)

@socketio.on('disconnect')
def handle_disconnect():
    print('Client disconnected')

if __name__ == '__main__':
    socketio.run(app, '127.0.0.1', 3000, debug=True)


