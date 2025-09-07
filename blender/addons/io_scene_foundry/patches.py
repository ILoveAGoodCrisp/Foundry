from pathlib import Path
import bpy

class ToolPatcher:
    def __init__(self, tool_path: str | Path):
        self.tool_path = str(tool_path)
        
    def _patch(self, offsets: list[bytes] | bytes, patches: list[bytes] | bytes, originals: list[bytes] | bytes):
        try:
            if not bpy.context.preferences.addons[__package__].preferences.allow_tool_patches:
                return
            
            if not isinstance(offsets, list):
                offsets = [offsets]
            
            if not isinstance(patches, list):
                patches = [patches] * len(offsets)
                
            if not isinstance(originals, list):
                originals = [originals] * len(offsets)
                
            assert len(offsets) == len(patches) == len(originals)
                
            with open(self.tool_path, "r+b") as f:
                for offset, patch, original in zip(offsets, patches, originals):
                    f.seek(offset)
                    data = f.read(len(original))
                    if data == original:
                        f.seek(offset)
                        f.write(patch)
        except:
            print("Failed to patch Tool")
        
    def reach_lightmap_color(self): 
        original0 = b"\xE8\x4D\x54\x29\x00"
        original1 = b"\xE8\x37\x54\x29\x00"
        original2 = b"\xE8\x1C\x54\x29\x00"
        original3 = b"\xE8\xC7\x53\x29\x00"
        original4 = b"\xE8\xB1\x53\x29\x00"
        original5 = b"\xE8\x96\x53\x29\x00"
        patch = b"\x90\x90\x90\x90\x90"
        address0 = 0xF2A02
        address1 = 0xF2A18
        address2 = 0xF2A33
        address3 = 0xF2A88
        address4 = 0xF2A9E
        address5 = 0xF2AB9
            
        self._patch([address0, address1, address2, address3, address4, address5], patch, [original0, original1, original2, original3, original4, original5])
        
    def reach_plane_builder(self):
        original = b"\x77"
        patch = b"\xEB"
        if self.tool_path.lower().endswith("_fast.exe"):
            address0 = 0x19A775
            address1 = 0x19A789
            address2 = 0x19A79A
        else:
            address0 = 0x220CE5
            address1 = 0x220D55
            address2 = 0x220DBB
            
        self._patch([address0, address1, address2], patch, original)
        
    def reach_wetness_data(self):
        original0 = b"\x74"
        patch0 = b"\xEB"
        original1 = b"\x25"
        patch1 = b"\x10"
        if self.tool_path.lower().endswith("_fast.exe"):
            return
        else:
            address0 = 0xB04F12
            address1 = 0x382557
            
        self._patch([address0, address1], [patch0, patch1], [original0, original1])