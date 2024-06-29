# !/usr/bin/env python
import asyncio
import base64
import json
import logging
import random
import sys
import time
from multiprocessing import Process, Queue

from PIL import Image
from flask import Flask, render_template, request, flash
from rgbmatrix import RGBMatrix, RGBMatrixOptions, graphics

from Expression import Expression

# Start process
global KillFlag
KillFlag = False

log = logging.getLogger('werkzeug')
log.setLevel(logging.INFO)


app = Flask(__name__, static_url_path="/static", static_folder="static")
app.secret_key = "YWoIkfT33hZV98Uoo8THajNYRhVYzYHK"
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
    files_content = []
    for file in os.listdir("expressions"):
        files_content.append(file)

    if (request.method == 'POST'):
        tempSetting = usrSettings.copy()
        for key in tempSetting.keys():
            newVal = request.form.get(key)
            try:
                newVal = int(newVal)
            except ValueError:
                print("[ERR] Not an int in Settings Save")
                pass
            tempSetting[key]["value"] = newVal

        with open('settings.json', 'w') as f:
            json.dump(tempSetting, f, indent=4)

        # Restart display after saving
        reloadDisplay()
        return "success", 200
    return render_template("settings.html", currentDisplay=curr_display, settings=usrSettings, expr=files_content)


@app.route('/editExpressions', methods=['POST'])
def editExpressions():
    # assuming the file paths are sent via a form data in POST request body
    if request.method == 'POST':
        filepaths = []
        for key, value in request.form.items():
            filepaths.append(key)
        for file_to_delete in filepaths:
            try:
                os.remove(os.path.join("expressions", file_to_delete))
            except FileNotFoundError:
                return "Error", 404
        return "success", 200


def reloadDisplay():
    global usrSettings, displayThread
    usrSettings = json.loads(open('settings.json').read())
    displayThread.terminate()
    displayThread.join()
    displayThread = Process(target=worker)
    displayThread.start()
    print("[DISPLAY] Reloaded Display")
    


## ENDFLASK

### DISPLAY

async def backgroundGifLoader(expression, matrix):
    newFrames = []
    gif = Image.open(expression.filename)
    print(f"[BACKGROUND] Loading {gif.n_frames} frames")
    for frame_index in range(0, gif.n_frames):
        gif.seek(frame_index)
        frame = gif.copy()
        frame.thumbnail((matrix.width, matrix.height))
        frame = frame.convert("RGB")
        canvas = matrix.CreateFrameCanvas()
        if usrSettings["Panel Treatment"]["value"] == 2:
            half_width = matrix.width // 2
            mirror_frame = frame.copy().transpose(Image.FLIP_LEFT_RIGHT).crop(
                (0, 0, min(frame.width, half_width), frame.height))
            frame = frame.crop((0, 0, min(frame.width, half_width), frame.height))
            offsetX = max(half_width - mirror_frame.width, 0)
            canvas.SetImage(frame, 0, 0)
            canvas.SetImage(mirror_frame, half_width + offsetX, 0)
        elif usrSettings["Panel Treatment"]["value"] == 1:
            half_width = matrix.width // 2
            frame = frame.crop((0, 0, min(frame.width, half_width), frame.height))
            offsetX = max(half_width - frame.width, 0)
            canvas.SetImage(frame, 0, 0)
            canvas.SetImage(frame, half_width + offsetX, 0)

        else:
            canvas.SetImage(frame)
        newFrames.append(canvas)
    gif.close()
    print(f"[BACKGROUND] Loaded {gif.n_frames} frames")
    return newFrames


def worker():
    try:
        global frames
        global usrSettings
        global KillFlag
        previousExpression = Expression("Nothing", "Pulsar", 20)
        options = RGBMatrixOptions()
        options.rows = usrSettings["Rows"]["value"]
        options.cols = usrSettings["Columns"]["value"]
        options.chain_length = usrSettings["Chain Length"]["value"]
        options.parallel = 1
        options.hardware_mapping = usrSettings["Remapping"]["choices"][usrSettings["Remapping"]["value"]]
        options.limit_refresh_rate_hz = usrSettings["Max Refresh Rate"]["value"]

        matrix = RGBMatrix(options=options)
        print(
            f"[DISPLAY] Starting new matrix with size {matrix.width}x{matrix.height} in {usrSettings['Panel Treatment']['choices'][usrSettings['Panel Treatment']['value']]}")
        loading = None
        frames = []

        while not KillFlag:
            expression = None
            memoryFrames = frames  # force only swap on last frame
            if not expression_queue.empty():
                expression = expression_queue.get()
            if expression is None:
                expression = previousExpression
            if expression == previousExpression:
                cur_frame = 0
                while cur_frame < len(memoryFrames):  # this does mean it can only swap on the last frame
                    matrix.SwapOnVSync(memoryFrames[cur_frame],
                                       framerate_fraction=usrSettings["Framerate Fraction"][
                                           "value"])  # framerate fraction = maxrefresh / integer = real fps. 
                    cur_frame += 1
            else:
                if str.lower(expression.filetype) == "gif":
                    # Load in background
                    frames = asyncio.run(backgroundGifLoader(expression, matrix))
                if str.lower(expression.filetype) == "png" or str.lower(
                        expression.filetype) == "jpg":  # no need to background because its literally 1 frame
                    frames.clear()
                    png = Image.open(expression.filename)
                    png.thumbnail((matrix.width, matrix.height))
                    png = png.convert("RGB")
                    canvas = matrix.CreateFrameCanvas()
                    if usrSettings["Panel Treatment"]["value"] == 2:
                        half_width = matrix.width // 2
                        mirror_frame = png.copy().transpose(Image.FLIP_LEFT_RIGHT).crop(
                            (0, 0, min(png.width, half_width), png.height))
                        frame = png.crop((0, 0, min(png.width, half_width), png.height))
                        offsetX = max(half_width - mirror_frame.width, 0)
                        canvas.SetImage(frame, 0, 0)
                        canvas.SetImage(mirror_frame, half_width + offsetX, 0)
                    elif usrSettings["Panel Treatment"]["value"] == 1:
                        half_width = matrix.width // 2
                        frame = png.crop((0, 0, min(png.width, half_width), png.height))
                        offsetX = max(half_width - frame.width, 0)
                        canvas.SetImage(frame, 0, 0)
                        canvas.SetImage(frame, half_width + offsetX, 0)
                    else:
                        canvas.SetImage(png)
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
    except KeyboardInterrupt:
        print("[DISPLAY] Shutting down")
        print("Bye :3")
        pass


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


def shutdown_server():
    func = request.environ.get('werkzeug.server.shutdown')
    if func is None:
        raise RuntimeError('Not running with the Werkzeug Server')
    func()


def print_name():
    print("\033[95m")
    print("    ____                ___           __")
    print("   / __ \___  ___ ___  / _ \_______  / /____")
    print("  / /_/ / _ \/ -_) _ \/ ___/ __/ _ \/ __/ _ \\")
    print("  \____/ .__/\__/_//_/_/  /_/  \___/\__/\___/ ")
    print("      /_/")
    print("\033[0m")
    print("\033[3mBecaue adding the \"-gen\" was just too much to ask for\033[0m")
    print("**--------------------------------------------------------------**")
    print("Brought to you by: \033[1m@Zemchar\033[0m")
    print("Open source & Licensed under GPLv3")
    print("Check out my other work: https://circuit-cat.com")
    print("Source Code Available Here: https://github.com/Zemchar/OpenProto")
    print("**--------------------------------------------------------------**\n")


# Press the green button in the gutter to run the script.
if __name__ == '__main__':
    global usrSettings
    KillFlag = False
    try:
        print_name()
        print("[INFO] Starting up...")
        # expression_queue.put(Expression("Nothing", "pulsar"))
        with open("settings.json") as settings_file:
            usrSettings = json.load(settings_file)
            print("[INFO] Settings loaded")
            settings_file.close()
        displayThread = Process(target=worker)
        displayThread.start()
        # supress flask messages
        app.run(host='0.0.0.0', port=80, debug=False)
    except KeyboardInterrupt:
        print("[INFO] Server shutting down...")
        KillFlag = True
        displayThread.terminate()
        displayThread.join()
        shutdown_server()
        print("Bye :3")
        time.sleep(2)
        sys.exit(0)
