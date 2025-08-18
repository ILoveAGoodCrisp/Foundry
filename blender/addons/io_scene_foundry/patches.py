from pathlib import Path

class ToolPatcher:
    def __init__(self, tool_path: str | Path):
        self.tool_path = str(tool_path)
        
    def _patch(self, offsets: list[bytes] | bytes, patches: list[bytes] | bytes, originals: list[bytes] | bytes):
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
        
    def reach_lightmap_color(self):
        patch = b"\xEB\x3D"
        original = b"\x73\x0C"
        if self.tool_path.lower().endswith("_fast.exe"):
            address0 = 0xF2A7F
            address1 = 0xF29F9
        else:
            address0 = 0x170956
            address1 = 0x17157F
            
        self._patch([address0, address1], patch, original)
        
    def reach_plane_builder(self):
        patch = b"\xEB"
        original = b"\x77"
        if self.tool_path.lower().endswith("_fast.exe"):
            address0 = 0x19A775
            address1 = 0x19A789
            address2 = 0x19A79A
        else:
            address0 = 0x220CE5
            address1 = 0x220D55
            address2 = 0x220DBB
            
        self._patch([address0, address1, address2], patch, original)