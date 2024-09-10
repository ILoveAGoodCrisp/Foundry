# ##### BEGIN MIT LICENSE BLOCK #####
#
# MIT License
#
# Copyright (c) 2024 Crisp
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

from math import sqrt
import os
import clr
from pathlib import Path

from mathutils import Vector
from ..managed_blam import Tag
from ..utils import print_warning
from .. import utils

class BitmapTag(Tag):
    tag_ext = 'bitmap'
    
    def _read_fields(self):
        self.longenum_usage = self.tag.SelectField('LongEnum:Usage')
        self.charenum_usage = self.tag.SelectField('CharEnum:curve mode')
        self.block_usage_override = self.tag.SelectField("Block:usage override")
        self.block_bitmaps = self.tag.SelectField("Block:bitmaps")
        
    def new_bitmap(self, bitmap_name, bitmap_type, color_space):
        def get_type_from_name(bitmap_name):
            suffix = bitmap_name.rpartition("_")[2].lower()
            if suffix and "_" in bitmap_name.strip("_"):
                if suffix.startswith(("orm", "mro", "mtr", "rmo", "control", "arm")):
                    return "Material Map"
                elif suffix.startswith("3d"):
                    return "3D Texture"
                elif suffix.startswith("blend"):
                    return "Blend Map (linear for terrains)"
                elif suffix.startswith("bump"):
                    return "Bump Map (from Height Map)"
                elif suffix.startswith(("cc", "change")):
                    return "Change Color Map"
                elif suffix.startswith("cube"):
                    return "Cube Map (Reflection Map)"
                elif suffix.startswith(("detailb", "detail_b")):
                    return "Detail Bump Map (from Height Map - fades out)"
                elif suffix.startswith(("detailn", "detail_n")):
                    return "Detail Normal Map"
                elif suffix.startswith("det"):
                    return "Detail Map"
                elif suffix.startswith("dsprite"):
                    return "Sprite (Double Multiply, Gray Background)"
                elif suffix.startswith("float"):
                    return "Float Map (WARNING)"
                elif suffix.startswith("height"):
                    return "Height Map (for Parallax)"
                elif suffix.startswith(("illum", "self", "emm")):
                    return "Self-Illum Map"
                elif suffix.startswith("msprite"):
                    return "Sprite (Blend, White Background)"
                elif suffix.startswith("spec"):
                    return "Specular Map"
                elif suffix.startswith("sprite"):
                    return "Sprite (Additive, Black Background)"
                elif suffix.startswith("ui"):
                    return "Interface Bitmap"
                elif suffix.startswith("vec"):
                    return "Vector Map"
                elif suffix.startswith("warp"):
                    return "Warp Map (EMBM)"
                elif suffix.startswith(("zbump", "dx_normal", 'dxnormal', 'normaldx', 'normal_dx')):
                    return "ZBrush Bump Map (from Bump Map)"
                elif suffix.startswith(("nor", "nm", "nrm")):
                    if self.corinth:
                        return "Normal Map (from Standard Orientation of Maya, Modo, Zbrush)"
                    else:
                        return "Normal Map (aka zbump)"
                    
            return "Diffuse Map"
        
        if bitmap_type == 'default':
            bitmap_type = get_type_from_name(bitmap_name)
            
        self.longenum_usage.SetValue(bitmap_type)
        self.charenum_usage.SetValue('force PRETTY')
        if not self.block_usage_override.Elements.Count:
             self.block_usage_override.AddElement()
        override = self.block_usage_override.Elements[0]
        # Running this command sets up needed default values for the bitmap type
        override.SelectField("reset usage override").RunCommand()
        source_gamma = override.SelectField('source gamma')
        source_gamma_value = self._source_gamma_from_color_space(color_space)
        if source_gamma_value:
            source_gamma.SetStringData(str(source_gamma_value))
        bitmap_curve = override.SelectField("bitmap curve")
        if source_gamma_value == 2.2:
            bitmap_curve.SetValue("sRGB (gamma 2.2)")
        elif source_gamma_value == 1:
            bitmap_curve.SetValue("linear")
            
        flags = override.SelectField("flags")
        flags.SetBit("Ignore Curve Override", True)
        bitmap_format = override.SelectField('bitmap format')
        if bitmap_type in ("Material Map", "Diffuse Map", "Blend Map (linear for terrains)", "Self-Illum Map", "Cube Map (Reflection Map)", "Detail Map"):
            bitmap_format.SetValue('DXT5 (Compressed Color + Compressed 8-bit Alpha)')
            if bitmap_type == 'Material Map':
                override.SelectField('mipmap limit').SetStringData('-1')
        elif bitmap_type in ("ZBrush Bump Map (from Bump Map)", "Normal Map (aka zbump)", "Normal Map (from Standard Orientation of Maya, Modo, Zbrush)"):
            bitmap_format.SetValue('DXN Compressed Normals (better)')
            
        self.tag_has_changes = True
        
    def save_to_tiff(self, blue_channel_fix=False, format='tiff'):
        def lerp(a, b, t):
            return a + (b - a) * t

        def calculate_z_vector(r, g):
            x = lerp(-1.0, 1.0, r)
            y = lerp(-1.0, 1.0, g)
            z = sqrt(max(0, 1 - x * x - y * y))

            return (z + 1) / 2
        # try:
        clr.AddReference('System.Drawing')
        from System import Array, Byte # type: ignore
        from System.Runtime.InteropServices import Marshal # type: ignore
        from System.Drawing import Rectangle # type: ignore
        from System.Drawing.Imaging import ImageLockMode, ImageFormat, PixelFormat # type: ignore
        game_bitmap = self._GameBitmap()
        bitmap = game_bitmap.GetBitmap()
        game_bitmap.Dispose()
        gamma = self.get_gamma_name()
        if bitmap.PixelFormat == PixelFormat.Format32bppArgb and (blue_channel_fix or gamma != 'xrgb'):
            # Correct for gamma space + add blue channel to normal maps
            # GameBitmap always outputs a bitmap in xrgb colorspace (gamma 2.0)
            bitmap_data = bitmap.LockBits(Rectangle(0, 0, bitmap.Width, bitmap.Height), ImageLockMode.ReadWrite, bitmap.PixelFormat)
            total_bytes = abs(bitmap_data.Stride) * bitmap_data.Height
            rgbValues = Array.CreateInstance(Byte, total_bytes)
            Marshal.Copy(bitmap_data.Scan0, rgbValues, 0, total_bytes)

            for i in range(0, total_bytes, 4):
                red = rgbValues[i + 2] / 255.0
                green = rgbValues[i + 1] / 255.0
                if gamma == 'linear':
                    red = red ** 2.0
                    green = green ** 2.0
                else:
                    red = utils.linear_to_srgb(red ** 2.0)
                    green = utils.linear_to_srgb(green ** 2.0)
                if blue_channel_fix:
                    blue = calculate_z_vector(red, green)
                else:
                    blue = rgbValues[i] / 255.0
                    if gamma == 'linear':
                        blue = blue ** 2.0
                    else:
                        blue = utils.linear_to_srgb(blue ** 2.0)
                        
                
                rgbValues[i + 2] = int(red * 255)
                rgbValues[i + 1] = int(green * 255)
                rgbValues[i] = int(blue * 255)

            Marshal.Copy(rgbValues, 0, bitmap_data.Scan0, total_bytes)
            bitmap.UnlockBits(bitmap_data)
                    
        tiff_path = str(Path(self.data_dir, self.tag.Path.RelativePath).with_suffix('.tiff'))
        tiff_dir = os.path.dirname(tiff_path)
        if not os.path.exists(tiff_dir):
            os.makedirs(tiff_dir, exist_ok=True)
        match format:
            case 'bmp':
                bitmap.Save(tiff_path, ImageFormat.Bmp)
            case 'png':
                bitmap.Save(tiff_path, ImageFormat.Png)
            case 'jpeg':
                bitmap.Save(tiff_path, ImageFormat.Jpeg)
            case 'tiff':
                bitmap.Save(tiff_path, ImageFormat.Tiff)
                
        bitmap.Dispose()
        # except:
        #     print_warning(f"Failed to Extract Bitmap from {self.tag_path.RelativePathWithExtension}")
        #     return
        return tiff_path
    
    def normal_type(self):
        return 'opengl' if self.longenum_usage.Value == 36 else 'directx'
    
    def has_bitmap_data(self):
        return self.block_bitmaps.Elements.Count
    
    def is_linear(self):
        bm = self.block_bitmaps.Elements[0]
        return bm.SelectField('curve').Value == 3
    
    def used_as_normal_map(self):
        bm = self.block_bitmaps.Elements[0]
        return bm.SelectField('format').Value == 38
    
    def get_gamma_name(self) -> str:
        bm = self.block_bitmaps.Elements[0]
        match bm.SelectField('curve').Value:
            case 3:
                return 'linear'
            case 5:
                return 'srgb'
            case _:
                return 'xrgb'
    
    def _source_gamma_from_color_space(self, color_space: str):
        match color_space:
            case 'sRGB':
                return 2.2
            case 'Non-Color':
                return 1.0