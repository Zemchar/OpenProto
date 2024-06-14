# This is a sample Python script.
# Press Shift+F10 to execute it or replace it with your code.
# Press Double Shift to search everywhere for classes, files, tool windows, actions, and settings.
# !/usr/bin/env python
import asyncio
import json
import random
import sys
import threading

import DisplayMethods
import base64
import time
from urllib import request
from flask import Flask, render_template, request, flash
from multiprocessing import Process, Queue
from rgbmatrix import RGBMatrix, RGBMatrixOptions, graphics
from PIL import Image
from Expression import Expression

global killFlag
killFlag = False
# Start process
app = Flask(__name__, static_url_path="/static", static_folder="static")
app.secret_key = "t4t"
import os

global displayThread
global curr_display
curr_display = "Nothing"
global expression_queue
expression_queue = Queue()
global usrSettings


#### FLASK
@app.route('/', methods=['GET', 'POST'])
def index():
    global curr_display
    files_content = {}
    flash("Loaded")
    for file in os.listdir("expressions"):
        with open(os.path.join("expressions", file), 'rb') as f:
            encoded_string = base64.b64encode(f.read()).decode()
            suffix = file.split('.')[-1]
            files_content[file] = f'data:image/{suffix};base64,' + encoded_string
    if request.method == 'POST':
        file = request.form.get("filename")
        expression_queue.put(Expression(os.path.join("expressions", file)))
        curr_display = file.split('.')[0]
        return "success", 200
    return render_template('expressionSelector.html', files=files_content, currentDisplay=curr_display)


@app.route('/fileUpload', methods=['GET', 'POST'])
def upload_file():
    global curr_display
    if request.method == 'POST':
        if 'file' not in request.files:
            return 'Error', 404
        file = request.files['file']
        file.save(os.path.join("expressions", file.filename))
        return "success", 200
    elif request.method == 'GET':
        return render_template("fileUpload.html", currentDisplay=curr_display)


@app.route('/textAnimator', methods=['GET', 'POST'])
def textAnimator():
    return render_template("textAnimationEditor.html", settings=usrSettings)


@app.route('/settings', methods=['GET', 'POST'])
def settings():
    # assuming the file paths are sent via a form data in POST request body
    if request.method == 'POST':
        print(request.form)
        filepaths = []
        for key, value in request.form.items():
            filepaths.append(key)
        for file_to_delete in filepaths:
            try:
                os.remove(os.path.join("expressions", file_to_delete))
            except FileNotFoundError:
                return "Error", 404
        return "success", 200
    files_content = []

    for file in os.listdir("expressions"):
        files_content.append(file)

    return render_template("settings.html", currentDisplay=curr_display, settings=usrSettings, expr=files_content)


## ENDFLASK

### DISPLAY

async def backgroundGifLoader(expression, matrix):
    newFrames = []
    gif = Image.open(expression.filename)
    print(f"[BACKGROUND] Loading {gif.n_frames} frames")
    for frame_index in range(0, gif.n_frames):
        gif.seek(frame_index)
        # must copy the frame out of the gif, since thumbnail() modifies the image in-place
        frame = gif.copy()
        frame.thumbnail((matrix.width, matrix.height))

        canvas = matrix.CreateFrameCanvas()
        canvas.SetImage(frame.convert("RGB"))
        newFrames.append(canvas)
    gif.close()
    print(f"[BACKGROUND] Loaded {gif.n_frames} frames")
    return newFrames


def worker():
    global frames
    global usrSettings
    previousExpression = Expression("Nothing", "Pulsar", 20)
    options = RGBMatrixOptions()
    options.rows = usrSettings["rows"]
    options.cols = usrSettings["columns"]
    options.chain_length = usrSettings["chain_count"]
    options.parallel = 1

    matrix = RGBMatrix(options=options)
    print(f"{matrix.width}x{matrix.height}")
    loading = None
    frames = []

    while True:
        expression = None
        memoryFrames = frames  # force only swap on last frame
        if not expression_queue.empty():
            expression = expression_queue.get()
        if expression is None:
            expression = previousExpression
        if expression == previousExpression:
            cur_frame = 0
            while cur_frame < len(memoryFrames):  # this does mean it can only swap on the last frame
                matrix.SwapOnVSync(memoryFrames[cur_frame], framerate_fraction=(40 if (expression.refreshrate == -1)
                                                                                else expression.refreshrate))
                cur_frame += 1
        else:
            if expression.filetype == "gif":
                # Load in background
                frames = asyncio.run(backgroundGifLoader(expression, matrix))
            if expression.filetype == "png":  # no need to background because its literally 1 frame
                frames.clear()
                png = Image.open(expression.filename)
                png.thumbnail((matrix.width, matrix.height))
                canvas = matrix.CreateFrameCanvas()
                canvas.SetImage(png.convert("RGB"))
                frames.append(canvas)
                matrix.Clear()
                png.close()
            elif expression.filetype == "pulsar":  # testing thingy
                frames.clear()
                for frame_index in range(0, 30):
                    canvas = matrix.CreateFrameCanvas()
                    for yPixel in range(0, 16):
                        for xPixel in range(0, options.cols * options.chain_length):
                            if random.random() < 0.3:
                                canvas.SetPixel(xPixel, yPixel, random.randint(0, 255),
                                                random.randint(0, 255),
                                                random.randint(0, 255))
                    frames.append(canvas)
                matrix.Clear()
            elif expression.filetype == "text-animation":
                frames = asyncio.run(backgroundTextLoader(expression, matrix))


async def backgroundTextLoader(expression, matrix):
    newFrames = []
    offscreen_canvas = matrix.CreateFrameCanvas()
    font = graphics.Font.fontLoad("fonts/7x13.bdf")
    xPos = offscreen_canvas.width
    yPos = 10
    textColor = graphics.Color(255, 255, 255)
    while True:
        offscreen_canvas.Clear()
        txt = graphics.DrawText(offscreen_canvas, font, xPos, yPos, textColor, expression.filename)
        xPos -= 1
        newFrames.append(offscreen_canvas)
        if xPos + txt < 0:
            newFrames.append(offscreen_canvas)
            break
    return newFrames


# Press the green button in the gutter to run the script.
if __name__ == '__main__':
    global usrSettings

    try:
        # expression_queue.put(Expression("Nothing", "pulsar"))
        with open("settings.json") as settings_file:
            usrSettings = json.load(settings_file)
            settings_file.close()
        displayThread = Process(target=worker)
        displayThread.start()
        app.run(host='0.0.0.0', port=80, debug=True)
    except KeyboardInterrupt:
        displayThread.terminate()
        time.sleep(2)
        sys.exit(0)
