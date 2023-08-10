# ##### BEGIN MIT LICENSE BLOCK #####
#
# MIT License
#
# Copyright (c) 2023 Crisp
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.
#
# ##### END MIT LICENSE BLOCK #####

from io_scene_foundry.managed_blam import ManagedBlam
import os

class ManagedBlamNewBitmap(ManagedBlam):
    def __init__(self, bitmap_name, bitmap_type):
        super().__init__()
        self.bitmap_name = bitmap_name
        self.bitmap_type = bitmap_type if bitmap_type else "default"
        self.tag_helper()

    def get_path(self):
        bitmaps_dir = os.path.join(self.asset_dir, "bitmaps")
        bitmap_path = os.path.join(bitmaps_dir, self.bitmap_name + ".bitmap")
        return bitmap_path

    def tag_edit(self, tag):
        if self.bitmap_type == "default":
            suffix = self.bitmap_name.rpartition("_")[2].lower()
            print(suffix)
            self.bitmap_type = "Diffuse Map"
            if suffix and "_" in self.bitmap_name.strip("_"):
                if suffix.startswith(("orm", "mro", "mtr", "rmo", "control")):
                    self.bitmap_type = "Material Map"
                elif suffix.startswith("3d"):
                    self.bitmap_type = "3D Texture"
                elif suffix.startswith("blend"):
                    self.bitmap_type = "Blend Map (linear for terrains)"
                elif suffix.startswith("bump"):
                    self.bitmap_type = "Bump Map (from Height Map)"
                elif suffix.startswith(("cc", "change")):
                    self.bitmap_type = "Change Color Map"
                elif suffix.startswith("cube"):
                    self.bitmap_type = "Cube Map (Reflection Map)"
                elif suffix.startswith(("detailb", "detail_b")):
                    self.bitmap_type = "Detail Bump Map (from Height Map - fades out)"
                elif suffix.startswith(("detailn", "detail_n")):
                    self.bitmap_type = "Detail Normal Map"
                elif suffix.startswith("det"):
                    self.bitmap_type = "Detail Map"
                elif suffix.startswith("dsprite"):
                    self.bitmap_type = "Sprite (Double Multiply, Gray Background)"
                elif suffix.startswith("float"):
                    self.bitmap_type = "Float Map (WARNING)"
                elif suffix.startswith("height"):
                    self.bitmap_type = "Height Map (for Parallax)"
                elif suffix.startswith(("illum", "self", "emm")):
                    self.bitmap_type = "Self-Illum Map"
                elif suffix.startswith("msprite"):
                    self.bitmap_type = "Sprite (Blend, White Background)"
                elif suffix.startswith("spec"):
                    self.bitmap_type = "Specular Map"
                elif suffix.startswith("sprite"):
                    self.bitmap_type = "Sprite (Additive, Black Background)"
                elif suffix.startswith("ui"):
                    self.bitmap_type = "Interface Bitmap"
                elif suffix.startswith("vec"):
                    self.bitmap_type = "Vector Map"
                elif suffix.startswith("warp"):
                    self.bitmap_type = "Warp Map (EMBM)"
                elif suffix.startswith(("zbump", "dx_normal")):
                    self.bitmap_type = "ZBrush Bump Map (from Bump Map)"
                elif suffix.startswith(("nor", "nm", "nrm")):
                    if self.corinth:
                        self.bitmap_type = "Normal Map (from Standard Orientation of Maya, Modo, Zbrush)"
                    else:
                        self.bitmap_type = "Normal Map (aka zbump)"


        usage_enum = tag.SelectField("LongEnum:Usage")
        usage_enum.SetValue(self.bitmap_type)
        curve_mode = tag.SelectField("CharEnum:curve mode")
        curve_mode.SetValue("force PRETTY")
        override_block = tag.SelectField("Block:usage override")
        # Check for existing usage override block so we don't overwrite
        if not override_block.Elements.Count:
            override_block.AddElement()
        override_element = override_block.Elements[0]
        reset = override_element.SelectField("reset usage override")
        reset.RunCommand()
        bitmap_curve = override_element.SelectField("bitmap curve")
        if bitmap_curve.Value == 1: # 1 is xRGB
            bitmap_curve.SetValue("sRGB (gamma 2.2)")
        flags = override_element.SelectField("flags")
        flags.SetBit("Ignore Curve Override", True)
        if self.bitmap_type in ("Material Map", "Diffuse Map", "Blend Map (linear for terrains)", "Self-Illum Map", "Cube Map (Reflection Map)", "Detail Map"):
            self.field_set_value_by_name(override_element, "bitmap format", "DXT5 (Compressed Color + Compressed 8-bit Alpha)")
        # flags.SetBit("Dont Allow Size Optimization", True)
        # dicer_flags = override_element.SelectField("dicer flags")
        # dicer_flags.SetBit("Color Grading sRGB Correction", True)