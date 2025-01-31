

from pathlib import Path

from .render_model import RenderModelTag

from ..managed_blam import Tag

class ModelTag(Tag):
    tag_ext = 'model'
    
    def _read_fields(self):
        self.reference_render_model = self.tag.SelectField("Reference:render model")
        self.reference_collision_model = self.tag.SelectField("Reference:collision model")
        self.reference_animation = self.tag.SelectField("Reference:animation")
        self.reference_physics_model = self.tag.SelectField("Reference:physics_model")
        self.block_variants = self.tag.SelectField("Block:variants")
        
    def get_model_paths(self, optional_tag_root=None) -> tuple[str]:
        """Returns string paths from model tag dependencies: render, collision, animation, physics"""
        render = ""
        collision = ""
        animation  = ""
        physics = ""
        render_path = self.reference_render_model.Path
        if render_path:
            if optional_tag_root:
                render = str(Path(optional_tag_root, render_path.RelativePathWithExtension))
            else:
                render = render_path.Filename
            
        collision_path = self.reference_collision_model.Path
        if collision_path:
            if optional_tag_root:
                collision = str(Path(optional_tag_root, collision_path.RelativePathWithExtension))
            else:
                render = collision_path.Filename
            
        animation_path = self.reference_animation.Path
        if animation_path:
            if optional_tag_root:
                animation = str(Path(optional_tag_root, animation_path.RelativePathWithExtension))
            else:
                render = animation_path.Filename
            
        physics_path = self.reference_physics_model.Path
        if physics_path:
            if optional_tag_root:
                physics = str(Path(optional_tag_root, physics_path.RelativePathWithExtension))
            else:
                render = physics_path.Filename
            
        return render, collision, animation, physics
                
    def set_model_overrides(self, render_model, collision_model, model_animation_graph, physics_model):
        if len(render_model) > 1 and self._tag_exists(render_model):
            tagpath_render_model = self._TagPath_from_string(Path(self.asset_dir, self.asset_name + ".render_model"))
            if self.reference_render_model.Path != tagpath_render_model:
                self.reference_render_model.Path = tagpath_render_model
                self.tag_has_changes = True
        if len(collision_model) > 1 and self._tag_exists(collision_model):
            tagpath_collision_model = self._TagPath_from_string(Path(self.asset_dir, self.asset_name + ".collision_model"))
            if self.reference_collision_model.Path != tagpath_collision_model:
                self.reference_collision_model.Path = tagpath_collision_model
                self.tag_has_changes = True
        if len(model_animation_graph) > 1 and self._tag_exists(model_animation_graph):
            tagpath_animation = self._TagPath_from_string(Path(self.asset_dir, self.asset_name + ".model_animation_graph"))
            if self.reference_animation != tagpath_animation:
                self.reference_animation.Path = tagpath_animation
                self.tag_has_changes = True
        if len(physics_model) > 1 and self._tag_exists(physics_model):
            tagpath_physics_model = self._TagPath_from_string(Path(self.asset_dir, self.asset_name + ".physics_model"))
            if self.reference_physics_model != tagpath_physics_model:
                self.reference_physics_model.Path = tagpath_physics_model
                self.tag_has_changes = True
            
    def get_model_variants(self):
        return [v.SelectField("name").GetStringData() for v in self.block_variants.Elements]
    
    def set_asset_paths(self):
        asset_render_model = Path(self.asset_dir, self.asset_name).with_suffix(".render_model")
        if self._tag_exists(asset_render_model):
            self.reference_render_model.Path = self._TagPath_from_string(asset_render_model)
        else:
            self.reference_render_model.Path = None
        
        asset_collision_model = Path(self.asset_dir, self.asset_name).with_suffix(".collision_model")
        if self._tag_exists(asset_collision_model):
            self.reference_collision_model.Path = self._TagPath_from_string(asset_collision_model)
        else:
            self.reference_collision_model.Path = None
        
        asset_model_animation_graph = Path(self.asset_dir, self.asset_name).with_suffix(".model_animation_graph")
        if self._tag_exists(asset_model_animation_graph):
            self.reference_animation.Path = self._TagPath_from_string(asset_model_animation_graph)
        else:
            self.reference_animation.Path = None
        
        asset_physics_model = Path(self.asset_dir, self.asset_name).with_suffix(".physics_model")
        if self._tag_exists(asset_physics_model):
            self.reference_physics_model.Path = self._TagPath_from_string(asset_physics_model)
        else:
            self.reference_physics_model.Path = None
            
        self.tag_has_changes = True
        
    def assign_lighting_info_tag(self, lighting_info_path: str):
        if not self.corinth: return
        info_tag_path = self._TagPath_from_string(lighting_info_path)
        info_field = self.tag.SelectField("Lighting Info")
        if info_field.Path != info_tag_path:
            info_field.Path = info_tag_path
            self.tag_has_changes = True
            
    def get_variant_regions_and_permutations(self, variant: str, state: int):
        region_permutations = set()
        if not variant:
            return region_permutations
        for element in self.block_variants.Elements:
            if element.Fields[0].GetStringData() != variant:
                continue
            
            render_path = self.reference_render_model.Path
            if render_path is None or not Path(render_path.Filename).exists():
                return region_permutations
            
            default_region = "default"
            region_default_perms = {}
            all_regions = set()
            all_permutations = set()
            
            with RenderModelTag(path=render_path.RelativePathWithExtension) as render:
                region_is_named_default = False
                perm_is_named_default = False
                for render_relement in render.block_regions.Elements:
                    region_name = render_relement.Fields[0].GetStringData()
                    all_regions.add(region_name)
                    if region_name == "default":
                        default_region = "default"
                        region_is_named_default = True
                    elif render_relement.ElementIndex == 0 and not region_is_named_default:
                        default_region = region_name
                        
                    for render_pelement in render_relement.SelectField("Block:permutations").Elements:
                        permutation_name = render_pelement.Fields[0].GetStringData()
                        all_permutations.add(permutation_name)
                        if permutation_name == "default":
                            region_default_perms[region_name] = "default"
                            perm_is_named_default = True
                        elif render_pelement.ElementIndex == 0 and not perm_is_named_default:
                            region_default_perms[region_name] = permutation_name
            
            variant_regions = set()
            for relement in element.SelectField("regions").Elements:
                region = relement.Fields[0].GetStringData()
                if region == "default":
                    region = default_region
                variant_regions.add(region)
                for pelement in relement.SelectField("permutations").Elements:
                    permutation = pelement.Fields[0].GetStringData()
                    if not permutation:
                        continue
                    elif permutation == "default":
                        permutation = region_default_perms.get(region, "default")
                        
                    region_permutations.add(tuple((region, permutation)))
                    
                    if state == 0:
                        continue

                    for selement in pelement.SelectField("states").Elements:
                        state_enum = selement.SelectField("ShortEnum:state").Value
                        if state == -1 or state == state_enum:
                            state = selement.Fields[0].GetStringData()
                            if state == "default":
                                state = region_default_perms.get(region, "default")
                            region_permutations.add(tuple((region, state)))
                        
            for reg in all_regions:
                if reg not in variant_regions:
                    for perm in all_permutations:
                        region_permutations.add(tuple((reg, perm)))
                        
            break
                            
        return region_permutations