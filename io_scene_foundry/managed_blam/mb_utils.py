import os
import bpy
from io_scene_foundry.utils.nwo_utils import get_ek_path

##### UTIL FUNCTIONS


def get_bungie(report):
    """Get a reference to Bungie"""
    mb_path = os.path.join(get_ek_path(), "bin", "managedblam")
    try:
        import clr

        try:
            clr.AddReference(mb_path)
            print(mb_path)
            if bpy.context.scene.nwo.game_version == "reach":
                import Bungie
            else:
                import Corinth as Bungie
        except:
            print("Failed to add reference to ManagedBlam")
            # return({'CANCELLED'})
    except:
        print("Failed to import clr")
        report(
            {
                "ERROR",
                "Failed to import modules to connect to ManagedBlam. Process aborted",
            }
        )

    return Bungie


def get_tag_and_path(Bungie, user_path):
    """Return the tag and bungie tag path for tag creation"""
    relative_path, tag_ext = get_path_and_ext(user_path)
    tag = Bungie.Tags.TagFile()
    tag_path = Bungie.Tags.TagPath.FromPathAndExtension(relative_path, tag_ext)

    return tag, tag_path


def get_path_and_ext(user_path):
    """Splits a file path into path and extension"""
    return user_path.rpartition(".")[0], user_path.rpartition(".")[2]
