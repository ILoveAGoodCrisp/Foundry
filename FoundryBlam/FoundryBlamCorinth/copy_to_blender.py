import os
import shutil

current_dir = os.path.dirname(os.path.realpath(__file__))
project_root = os.path.dirname(os.path.dirname(current_dir))
output_exe = os.path.join(current_dir, "bin", "x64", "Debug", "FoundryBlamCorinth.exe")
target = os.path.join(project_root, "blender", "addons", "io_scene_foundry", "managed_blam", "FoundryBlam", "FoundryBlamCorinth.exe")

shutil.copyfile(output_exe, target)