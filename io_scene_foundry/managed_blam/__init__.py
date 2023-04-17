
from io_scene_foundry.utils.nwo_utils import print_warning
import bpy
from bpy.types import Operator
from bpy.app.handlers import persistent

def callback():
    pass

# def create_shader_tag(blender_material):
#     # Check if bitmaps exist already, if not, create them
    
#     from tag_shader import TagShader
#     tag = TagShader()

class ManagedBlam_Init(Operator):
    """Initialises Managed Blam and locks the currently selected game"""
    bl_idname = "managed_blam.init"
    bl_label = "Managed Blam"
    bl_options = {'REGISTER'}
    bl_options = {'UNDO', 'PRESET'}
    bl_description = "Initialises Managed Blam and locks the currently selected game"

    def callback(self):
        pass

    def execute(self, context):
        from io_scene_foundry.utils.nwo_utils import get_ek_path
        import sys
        import os
        import subprocess
        import ctypes

        # append the blender python module path to the sys PATH
        packages_path = os.path.join(sys.exec_prefix, 'lib', 'site-packages')
        sys.path.append(packages_path)
        # Get the reference to ManagedBlam.dll
        mb_path = os.path.join(get_ek_path(), 'bin', 'managedblam')

        # Check that a path to ManagedBlam actually exists
        if not os.path.exists(f'{mb_path}.dll'):
            print_warning("Could not find path to ManagedBlam.dll")
            return ({'CANCELLED'})
        
        # Logic for importing the clr module and importing Bungie/Corinth from ManagedBlam.dll
        try:
            import clr
            try:
                clr.AddReference(mb_path)
                print(mb_path)
                if bpy.context.scene.nwo_global.game_version == 'reach':
                    import Bungie
                    print("Import Bungie")
                else:
                    import Corinth as Bungie
                    print("Imported Corinth as Bungie")
            except:
                print('Failed to add reference to ManagedBlam')
                return({'CANCELLED'})
        except:
            print("Couldn't find clr module, attempting pythonnet install")
            print("Blender Version: " + bpy.app.version_string)
            if bpy.app.version < (3, 4, 0):
                ctypes.windll.user32.MessageBoxW(0, "Your blender version (" + bpy.app.version_string + ") is too old. Minimum required version is 3.4.0 to install Pythonnet for ManagedBlam.", f"Blender Version Too Old", 0)
                return({'CANCELLED'})
            else:
                try:
                    subprocess.check_call([sys.executable, "-m", "pip", "install", 'pythonnet'])
                    print("Succesfully installed necessary modules")
                    open(os.path.join(bpy.app.tempdir, 'blam_new.txt'), 'x')
                    ctypes.windll.user32.MessageBoxW(0, "Pythonnet module installed for Blender. Please restart Blender to use ManagedBlam.", f"Pythonnet Installed for Blender", 0)
                except:
                    print('Failed to install pythonnet')
                    return({'CANCELLED'})
                else:
                    return({'FINISHED'})

        else:
            # Initialise ManagedBlam     
            print("Initialising ManagedBlam...")
            try:
                startup_parameters = Bungie.ManagedBlamStartupParameters()
                startup_parameters.InistializationLevel = Bungie.InitializationType.TagsOnly
                Bungie.ManagedBlamSystem.Start(get_ek_path(), self.callback(), startup_parameters)
            except:
                print("ManagedBlam already intialised. Skipping")
                return({'CANCELLED'})
            else:
                print("Success!")
                print("game_version locked")
                open(os.path.join(bpy.app.tempdir, 'blam.txt'), 'x')
                return({'FINISHED'})

def register():
    bpy.utils.register_class(ManagedBlam_Init)

def unregister():
    bpy.utils.unregister_class(ManagedBlam_Init)
    
if __name__ == '__main__':
    register()


