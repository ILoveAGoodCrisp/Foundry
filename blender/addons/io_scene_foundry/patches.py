from pathlib import Path


class ToolPatcher:
    def __init__(self, tool_path: str | Path):
        self.tool_path = str(tool_path)
        
    def _patch(self, offsets: list[bytes] | bytes, patches: list[bytes] | bytes):
        if not isinstance(offsets, list):
            offsets = [offsets]
        
        if not isinstance(patches, list):
            patches = [patches] * len(offsets)
            
        assert len(offsets) == len(patches)
            
        with open(self.tool_path, "r+b") as f:
            for offset, patch in zip(offsets, patches):
                f.seek(offset)
                data = f.read(len(patch))
                if data != patch:
                    f.seek(offset)
                    f.write(patch)
        
    def reach_lightmap_color(self):
        patch = b"\xEB\x3D"
        if self.tool_path.lower().endswith("_fast.exe"):
            address0 = 0xF2A7F
            address1 = 0xF29F9
        else:
            address0 = 0x170956
            address1 = 0x17157F
            
        self._patch([address0, address1], patch)