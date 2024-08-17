from ctypes import pointer
import os
from pathlib import Path
import tempfile
from .functions import *
from .formats import *
from . import Granny, new_callback_function



def new_granny(filename: str):
    os.chdir(r"F:\Modding\Main\HREK")
    granny = Granny("F:\Modding\Main\HREK\granny2_x64.dll")
    print(granny.get_version_string())
    granny.create_callback()
    granny.create_file_info(filename)
    
    granny.create_materials()
    granny.create_skeletons()
    granny.save()
    