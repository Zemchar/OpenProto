import random

from rgbmatrix import RGBMatrix, RGBMatrixOptions
from PIL import Image
import sys
global killFlag
killFlag = False
from main import expression_queue
from Expression import Expression





def killDisplayThread():
    global killFlag
    killFlag = True
