

from ctypes import c_void_p
from math import sqrt
import math
import os
import clr
from pathlib import Path

from mathutils import Vector

from ..constants import NormalType
from ..managed_blam import Tag
from .. import utils

clr.AddReference('System.Drawing')
from System import Array, Byte # type: ignore
from System.Runtime.InteropServices import Marshal # type: ignore
from System.Drawing import Rectangle, Bitmap # type: ignore
from System.Drawing.Imaging import ImageLockMode, ImageFormat, PixelFormat # type: ignore

path_cache = set()

def clear_path_cache():
    global path_cache
    path_cache.clear()

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
        
    def get_granny_data(self, fill_alpha: bool, calc_blue_channel: bool) -> object | None:
        clr.AddReference('System.Drawing')
        from System import Array, Byte # type: ignore
        from System.Runtime.InteropServices import Marshal # type: ignore
        from System.Drawing import Rectangle # type: ignore
        from System.Drawing.Imaging import ImageLockMode, PixelFormat # type: ignore
        from System.Runtime.InteropServices import GCHandle, GCHandleType # type: ignore
        game_bitmap = self._GameBitmap()
        bitmap = game_bitmap.GetBitmap()
        game_bitmap.Dispose()
        
        if bitmap.PixelFormat != PixelFormat.Format32bppArgb:
            return None
        
        gamma = self.get_gamma_name()
        
        width = bitmap.Width
        height = bitmap.Height

        bitmap_data = bitmap.LockBits(Rectangle(0, 0, width, height), ImageLockMode.ReadWrite, bitmap.PixelFormat)
        stride = bitmap_data.Stride
        total_bytes = abs(stride) * height
        bgra_array = Array.CreateInstance(Byte, total_bytes)
        Marshal.Copy(bitmap_data.Scan0, bgra_array, 0, total_bytes)
        bitmap.UnlockBits(bitmap_data)
        
        if calc_blue_channel:
            rgba_array = self.bgra_to_rgba_with_calculated_blue(total_bytes, bgra_array, gamma)
        elif fill_alpha:
            rgba_array = self.bgra_to_rgba_solid_alpha(total_bytes, bgra_array, gamma)
        else:
            rgba_array = self.bgra_to_rgba(total_bytes, bgra_array, gamma)
        
        handle = GCHandle.Alloc(rgba_array, GCHandleType.Pinned)
        rgba_ptr = None
        try:
            rgba_ptr = c_void_p(handle.AddrOfPinnedObject().ToInt64())
        finally:
            if handle.IsAllocated:
                handle.Free()
        
        bitmap.Dispose()
        
        if rgba_ptr is None:
            return None
        
        return width, height, stride, rgba_ptr
    
    @staticmethod
    def bgra_to_rgba_solid_alpha(total_bytes, bgra_array, gamma):
        for i in range(0, total_bytes, 4):
            bgra_array[i + 3] = 255
            red = bgra_array[i + 2] / 255.0
            green = bgra_array[i + 1] / 255.0
            blue = bgra_array[i] / 255.0
            # match gamma:
            #     case 'linear':
            #         red = red ** 2.0
            #         green = green ** 2.0
            #         blue = blue ** 2.0
            #     case 'srgb':
            #         red = utils.linear_to_srgb(red ** 2.0)
            #         green = utils.linear_to_srgb(green ** 2.0)
            #         blue = utils.linear_to_srgb(blue ** 2.0)
                    
            bgra_array[i] = int(red * 255)
            bgra_array[i + 1] = int(green * 255)
            bgra_array[i + 2] = int(blue * 255)
            
        return bgra_array
    
    @staticmethod
    def bgra_to_rgba(total_bytes, bgra_array, gamma):
        for i in range(0, total_bytes, 4):
            red = bgra_array[i + 2] / 255.0
            green = bgra_array[i + 1] / 255.0
            blue = bgra_array[i] / 255.0
            # match gamma:
            #     case 'linear':
            #         red = red ** 2.0
            #         green = green ** 2.0
            #         blue = blue ** 2.0
            #     case 'srgb':
            #         red = utils.linear_to_srgb(red ** 2.0)
            #         green = utils.linear_to_srgb(green ** 2.0)
            #         blue = utils.linear_to_srgb(blue ** 2.0)
                    
            bgra_array[i] = int(red * 255)
            bgra_array[i + 1] = int(green * 255)
            bgra_array[i + 2] = int(blue * 255)
            
        return bgra_array
    
    @staticmethod
    def bgra_to_rgba_with_calculated_blue(total_bytes, bgra_array, gamma):
        for i in range(0, total_bytes, 4):
            red = bgra_array[i + 2] / 255.0
            green = bgra_array[i + 1] / 255.0
            blue = calculate_z_vector(red, green)
            match gamma:
                case 'linear':
                    red = red ** 2.0
                    green = green ** 2.0
                    blue = blue ** 2.0
                case 'srgb':
                    red = utils.linear_to_srgb(red ** 2.0)
                    green = utils.linear_to_srgb(green ** 2.0)
                    blue = utils.linear_to_srgb(blue ** 2.0)
                    
            bgra_array[i] = int(red * 255)
            bgra_array[i + 1] = int(green * 255)
            bgra_array[i + 2] = int(blue * 255)
            
        return bgra_array
    
        # faces = {
        #     "back": bitmap.Clone(Rectangle(f * 3, f, f, f), bitmap.PixelFormat), # CUBEMAP: 0,1 HALO: 3,1
        #     "left": bitmap.Clone(Rectangle(0, f, f, f), bitmap.PixelFormat), # CUBEMAP: 1,1 HALO: 0,1
        #     "front": bitmap.Clone(Rectangle(f, f, f, f), bitmap.PixelFormat), # CUBEMAP: 2,1 HALO: 1,1
        #     "right": bitmap.Clone(Rectangle(2 * f, f, f, f), bitmap.PixelFormat), # CUBEMAP: 3,1 HALO: 2,1
        #     "bottom": bitmap.Clone(Rectangle(0, 2 * f, f, f), bitmap.PixelFormat), # CUBEMAP: 1,2 HALO: 0, 2
        #     "top": bitmap.Clone(Rectangle(0, 0, f, f), bitmap.PixelFormat), # CUBEMAP: 1,0 HALO: 0,0
        # }


    def extract_faces(self, cubemap, face_size):
        faces = {
            "+Y": cubemap.Clone(Rectangle(0, 0, face_size, face_size), cubemap.PixelFormat),
            "-Y": cubemap.Clone(Rectangle(0, 2 * face_size, face_size, face_size), cubemap.PixelFormat),
            "+Z": cubemap.Clone(Rectangle(0, face_size, face_size, face_size), cubemap.PixelFormat),
            "-Z": cubemap.Clone(Rectangle(2 * face_size, face_size, face_size, face_size), cubemap.PixelFormat),
            "+X": cubemap.Clone(Rectangle(face_size, face_size, face_size, face_size), cubemap.PixelFormat),
            "-X": cubemap.Clone(Rectangle(3 * face_size, face_size, face_size, face_size), cubemap.PixelFormat)
        }
        return faces

    def sample_cubemap(self, faces, theta, phi, face_size):
        x = math.cos(phi) * math.cos(theta)
        y = math.sin(phi)
        z = math.cos(phi) * math.sin(theta)

        abs_x, abs_y, abs_z = abs(x), abs(y), abs(z)

        if abs_y >= abs_x and abs_y >= abs_z:
            face = "+Y" if y > 0 else "-Y"
            u = (x / abs_y + 1) / 2
            v = (z / abs_y + 1) / 2
        elif abs_x >= abs_y and abs_x >= abs_z:
            face = "+X" if x > 0 else "-X"
            u = (-z / abs_x + 1) / 2
            v = (-y / abs_x + 1) / 2
        else:
            face = "+Z" if z > 0 else "-Z"
            u = (x / abs_z + 1) / 2
            v = (-y / abs_z + 1) / 2

        u = max(0, min(int(u * (face_size - 1)), face_size - 1))
        v = max(0, min(int(v * (face_size - 1)), face_size - 1))

        return faces[face].GetPixel(u, v)

    def cubemap_to_equirectangular(self, bitmap):
        """ Converts a left-shifted cross cubemap (wrapping -X) to an equirectangular projection """
        width = bitmap.Width
        height = bitmap.Height
        face_size = height // 3
        faces = self.extract_faces(bitmap, face_size)
        
        # Define output image size (2:1 aspect ratio)
        equirect_width = face_size * 8
        equirect_height = equirect_width // 2

        # Create new equirectangular image
        equirect = Bitmap(equirect_width, equirect_height)
        
        for y in range(equirect_height):
            phi = ((equirect_height - 1 - y) / equirect_height - 0.5) * math.pi  # Flip Y

            for x in range(equirect_width):
                theta = (x / equirect_width) * 2 * math.pi - math.pi  # -π to π
                color = self.sample_cubemap(faces, theta, phi, face_size)
                equirect.SetPixel(x, y, color)
                
        return equirect
    
    def _convert_cubemap(self, bitmap, suffix):
        equirect = self.cubemap_to_equirectangular(bitmap)
        return equirect, str(Path(self.data_dir, f"{self.tag_path.RelativePath}{suffix}_equirectangular").with_suffix('.tiff'))
    
    def _save_single(self, blue_channel_fix: bool, format: str, frame_index: int, suffix: str):
        game_bitmap = self._GameBitmap(frame_index=frame_index)
        bitmap = game_bitmap.GetBitmap()
        game_bitmap.Dispose()
        
        if bitmap.PixelFormat == PixelFormat.Format32bppArgb and blue_channel_fix:
            bitmap_data = bitmap.LockBits(Rectangle(0, 0, bitmap.Width, bitmap.Height), ImageLockMode.ReadWrite, bitmap.PixelFormat)
            total_bytes = abs(bitmap_data.Stride) * bitmap_data.Height
            rgbValues = Array.CreateInstance(Byte, total_bytes)
            Marshal.Copy(bitmap_data.Scan0, rgbValues, 0, total_bytes)

            for i in range(0, total_bytes, 4):
                red = rgbValues[i + 2] / 255.0
                green = rgbValues[i + 1] / 255.0
                blue = rgbValues[i] / 255.0
                red = red ** 2.2
                green = green ** 2.2
                blue = calculate_z_vector(red, green)
                rgbValues[i + 2] = int(red * 255)
                rgbValues[i + 1] = int(green * 255)
                rgbValues[i] = int(blue * 255)

            Marshal.Copy(rgbValues, 0, bitmap_data.Scan0, total_bytes)
            bitmap.UnlockBits(bitmap_data)
        
        tiff_path = str(Path(self.data_dir, self.tag_path.RelativePath).with_suffix('.tiff'))
        if suffix: # we're dealing with a plate
            save_path = str(Path(self.data_dir, self.tag_path.RelativePath, f"{self.tag_path.ShortName}{suffix}").with_suffix('.tiff'))
        else:
            save_path = tiff_path
            
        tiff_dir = os.path.dirname(save_path)
        
        if not os.path.exists(tiff_dir):
            os.makedirs(tiff_dir, exist_ok=True)
        if self.is_cubemap:
            # save the original cubemap
            match format:
                case 'bmp':
                    bitmap.Save(save_path, ImageFormat.Bmp)
                case 'png':
                    bitmap.Save(save_path, ImageFormat.Png)
                case 'jpeg':
                    bitmap.Save(save_path, ImageFormat.Jpeg)
                case 'tiff':
                    bitmap.Save(save_path, ImageFormat.Tiff)
            bitmap, tiff_path = self._convert_cubemap(bitmap, suffix)
            save_path = tiff_path

        match format:
            case 'bmp':
                bitmap.Save(save_path, ImageFormat.Bmp)
            case 'png':
                bitmap.Save(save_path, ImageFormat.Png)
            case 'jpeg':
                bitmap.Save(save_path, ImageFormat.Jpeg)
            case 'tiff':
                bitmap.Save(save_path, ImageFormat.Tiff)
                
        bitmap.Dispose()
        return tiff_path
        
    def save_to_tiff(self, blue_channel_fix=False, format='tiff') -> list[str]:
        global path_cache
        expected_tiff_path = Path(self.data_dir, self.tag_path.RelativePath).with_suffix('.tiff')
        expected_tif_path = expected_tiff_path.with_suffix('.tif')
        if expected_tiff_path in path_cache and expected_tiff_path.exists():
            return expected_tiff_path
        elif expected_tif_path in path_cache and expected_tif_path.exists():
            return expected_tif_path
        
        self.is_cubemap = "cube" in self.tag_path.ShortName
        if self.block_bitmaps.Elements.Count <= 0:
            return
        gamma = self.get_gamma_value()
        if not blue_channel_fix and gamma == 1.95: #dxt5
            self.block_bitmaps.Elements[0].SelectField("CharEnum:curve").Value = 5
        bitmap_elements = self.block_bitmaps.Elements
        if bitmap_elements.Count > 1:
            array_length = bitmap_elements.Count
            for element in bitmap_elements:
                temp_path = self._save_single(blue_channel_fix, format, element.ElementIndex, f"_{element.ElementIndex + 1:05}")
                if element.ElementIndex == 0:
                    tiff_path = temp_path
            
            
            if not self.is_cubemap:
                full_tiff_path = Path(tiff_path)
                utils.run_tool(["plate", str(full_tiff_path.with_suffix(""))], null_output=True)
                tif_path = full_tiff_path.with_suffix(".tif")
                if tif_path.exists():
                    return str(tif_path) 
        else:
            tiff_path = self._save_single(blue_channel_fix, format, 0, "")
        
        
        path_cache.add(tiff_path)
        return tiff_path
    
    def normal_type(self):
        return NormalType.OPENGL if self.longenum_usage.Value == 36 else NormalType.DIRECTX
    
    def has_bitmap_data(self):
        return self.block_bitmaps.Elements.Count
    
    def is_linear(self):
        bm = self.block_bitmaps.Elements[0]
        return bm.SelectField('curve').Value == 3
    
    def used_as_normal_map(self):
        return self.longenum_usage.Value in {2, 3, 18, 19, 20, 21, 36, 38}
    
    def uses_srgb(self):
        return self.longenum_usage.Value in {0, 5, 7}
    
    def get_gamma_name(self) -> str:
        bm = self.block_bitmaps.Elements[0]
        match bm.SelectField('curve').Value:
            case 3:
                return 'linear'
            case 5:
                return 'srgb'
            case _:
                return 'xrgb'
            
    def get_gamma_value(self) -> str:
        bm = self.block_bitmaps.Elements[0]
        match bm.SelectField('curve').Value:
            case 0:
                return 1.95
            case 1:
                return 1.95
            case 2:
                return 2.0
            case 3:
                return 1.0
            case 4:
                return 1.0
            case 5:
                return 2.2
    
    def _source_gamma_from_color_space(self, color_space: str):
        match color_space:
            case 'sRGB':
                return 2.2
            case 'Non-Color':
                return 1.0
            
def lerp(p1: float, p2: float, fraction: float) -> float:
    return (p1 * (1 - fraction)) + (p2 * fraction)

def calculate_z_vector(r: float, g: float) -> float:
    x = lerp(-1.0, 1.0, r)
    y = lerp(-1.0, 1.0, g)
    z = sqrt(max(0, 1 - x * x - y * y))

    return (z + 1) / 2