class SpecialMaterial:
    """Class holding information about materials that get special treatment at export"""
    def __init__(self, name: str, games: list, asset_types: list, color: list[float], shader_path: str, is_face_property: bool):
        self.name = name
        self.games = games
        self.asset_types = asset_types
        self.color = color
        self.shader_path = shader_path
        self.is_face_property = is_face_property
    
invisible = SpecialMaterial('+invisible', ['reach', 'h4'], ['MODEL', 'SKY', 'SCENARIO', 'PREFAB'], [1, 1, 1, 0], r'objects\levels\shared\shaders\invisible', False)
invalid = SpecialMaterial('+invalid', ['reach', 'h4'], ['MODEL', 'SKY', 'SCENARIO', 'PREFAB'], [0.5, 0.5, 0.5, 1], r'shaders\invalid', False)
missing = SpecialMaterial('+missing', ['h4',], ['MODEL', 'SKY', 'SCENARIO', 'PREFAB'], [1, 0, 1, 1], r'shaders\missing', False)
seamsealer = SpecialMaterial('+seamsealer', ['reach',], ['SCENARIO',], [1, 1, 1, 0.05], 'bungie_face_type=_connected_geometry_face_type_seam_sealer', True)
sky = SpecialMaterial('+sky', ['reach',], ['SCENARIO',], [0.5, 0.7, 1, 0.05], 'bungie_face_type=_connected_geometry_face_type_sky', True)
collision = SpecialMaterial('+collision', ['reach',], ['SCENARIO',], [0.0, 1.0, 0.0, 0.2], 'bungie_face_mode=_connected_geometry_face_mode_collision_only', True)
sphere_collision = SpecialMaterial('+sphere_collision', ['reach',], ['SCENARIO',], [0.0, 0.0, 1.0, 0.2], 'bungie_face_mode=_connected_geometry_face_mode_sphere_collision_only', True)

special_materials = invisible, invalid, missing, seamsealer, sky, collision, sphere_collision

class ConventionMaterial:
    """Class holding information about materials that get a color assigned to them and cannot be given a shader path, but otherwise have no special properties. At export these are forced to override/invisible"""
    def __init__(self, name: str, color: list[float]):
        self.name = name
        self.color = color
        
InvisibleSky = ConventionMaterial('InvisibleSky', [0.5, 0.7, 1, 0.05])
Physics = ConventionMaterial('Physics', [0.0, 0.0, 1.0, 0.2])
Seam = ConventionMaterial('Seam', [0.4, 1.0, 0.4, 0.6])
Portal = ConventionMaterial('Portal', [0.8, 0.7, 0.2, 0.1])
Collision = ConventionMaterial('Collision', [0.0, 1.0, 0.0, 0.2])
PlayCollision = ConventionMaterial('PlayCollision', [1.0, 0.5, 0.0, 0.2])
WallCollision = ConventionMaterial('WallCollision', [0.0, 0.8, 0.0, 0.2])
BulletCollision = ConventionMaterial('BulletCollision', [0.0, 0.8, 0.8, 0.2])
CookieCutter = ConventionMaterial('CookieCutter', [1.0, 0.1, 0.9, 0.2])
Fog = ConventionMaterial('Fog', [0.3, 0.3, 1.0, 0.2])
# RainBlocker = ConventionMaterial('RainBlocker', [0.3, 0.3, 1.0, 1.0])
# RainSheet = ConventionMaterial('RainSheet', [0.3, 0.3, 1.0, 1.0])
WaterVolume = ConventionMaterial('WaterVolume', [0.0, 0.0, 1.0, 0.9])
Structure = ConventionMaterial('Structure', [0.0, 0.0, 1.0, 0.9])
SoftCeiling = ConventionMaterial('SoftCeiling', [0.5, 0.4, 0.1, 0.9])
SoftKill = ConventionMaterial('SoftKill', [0.5, 0.0, 0.1, 0.9])
SlipSurface = ConventionMaterial('SlipSurface', [0.3, 0.5, 0.2, 0.9])
StreamingVolume = ConventionMaterial('StreamingVolume', [1, 1, 1, 0.3])
LightmapExcludeVolume = ConventionMaterial('LightmapExcludeVolume', [0, 1, 1, 0.3])
        
convention_materials = (InvisibleSky, Physics, Seam, Portal, Collision, PlayCollision, WallCollision, BulletCollision, 
                        CookieCutter, Fog, WaterVolume, Structure, SoftCeiling, SoftKill, SlipSurface, StreamingVolume, LightmapExcludeVolume)