"""Halo 3/ODST seam material names, independent of Blender."""
import re


def seam_material_name(name):
    """Retain a named seam's BSP identity without flags or Blender copy suffixes."""
    name = re.sub(r'\.\d{3,}$', '', name.strip())
    if not name.casefold().startswith('+seam:'):
        return None
    name = re.sub(r'\b(?:lm|lp|hl|ds|pf|lt|to|at|ro):\S+', '', name).strip()
    bsp = name.partition(':')[2].rstrip("%#?!@*$^-&=.;)><|~({]}[' ")
    return '+seam:' + bsp if bsp else None
