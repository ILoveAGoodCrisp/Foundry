from collections import defaultdict
from datetime import datetime
from getpass import getuser
import os
from pathlib import Path
import bpy
import xml.etree.cElementTree as ET
import xml.dom.minidom

from .cinematic import Actor

from ..props.scene import NWO_ScenePropertiesGroup
from ..tools.asset_types import AssetType
from ..tools.animation.composites import CompositeXML

from ..utils import (
    get_data_path,
    is_corinth,
    relative_path,
)
from .. import utils

class SidecarFileData:
    gr2_path: Path
    blend_path: Path
    permutation: str
    
    def __init__(self, gr2_path: str, blend_path: str, permutation: str = "default", region: str = "default"):
        self.gr2_path = gr2_path
        self.blend_path = blend_path
        self.permutation = permutation
        self.region = region
        # Animation Only
        self.name = "any idle"
        self.compression = "Default"
        self.animation_type = "base"
        self.movement = "none"
        self.space = "object"
        self.pose_overlay = False
        self.is_pca = False
        # Cinematic only
        self.frame_start = 0
        self.frame_end = 0
        self.shot_index = 0
        

class Sidecar:
    def __init__(self, sidecar_path_full: Path, sidecar_path: Path, asset_path: Path, asset_name: str, asset_type: AssetType, scene_settings: NWO_ScenePropertiesGroup, corinth: bool, context: bpy.types.Context, tags_dir=None):
        self.reach_world_animations = set()
        self.pose_overlays = set()
        self.relative_asset_path = relative_path(asset_path)
        self.tag_path = relative_path(Path(asset_path, asset_name))
        self.asset_path = asset_path
        self.asset_name = asset_name
        self.asset_type = asset_type
        self.tags_dir = tags_dir
        self.data_dir = Path(utils.get_data_path())
        self.sidecar_path = sidecar_path
        self.sidecar_path_full = sidecar_path_full
        self.relative_blend = bpy.data.filepath
        self.relative_blend = str(Path(bpy.data.filepath).relative_to(get_data_path())) if Path(bpy.data.filepath).is_relative_to(get_data_path()) else bpy.data.filepath
        self.external_blend = self.relative_blend == bpy.data.filepath
        self.scene_settings = scene_settings
        self.animation_composites = []
        self.corinth = corinth
        self.context = context
        self.nwo = utils.get_scene_props()
        self.lods = set()
        
        self.clone = None
        self.verification = None
        
        self.structure = set()
        self.design = set()
        self.has_armature = False
        self.regions = []
        self.global_materials = []
        self.file_data: dict[list[SidecarFileData]] = defaultdict(list)
        self.child_sidecar_paths = []
        self.child_animation_elements = []
        self.child_physics_elements = []
        self.child_collision_elements = []
        self.child_render_elements = []
        self.child_bsp_elements = []
        self.child_scene_elements = []
        self.cinematic_scenes = []
        # self.parent_sidecar = parent_sidecar
        # self.parent_sidecar_relative = None if parent_sidecar is None else utils.relative_path(parent_sidecar)
        
    def create_actor_sidecar(self, actor: Actor, blend_path: Path):
        # This is awful but ultimately the best solution given the modder workflow
        actor_asset_path = Path(actor.sidecar)
        actor_sidecar_path_relative = Path(f"{actor.sidecar}.sidecar.xml")
        actor_sidecar_path_full = Path(self.data_dir, actor_sidecar_path_relative)
        actor_sidecar = Sidecar(actor_sidecar_path_full, actor_sidecar_path_relative, actor_asset_path, actor_asset_path.name, AssetType.MODEL, None, self.corinth, self.context, self.tags_dir)
        actor_sidecar.build(actor_render_model_path=actor.render_model)
        
    def add_file_data(self, tag_type: str, permutation: str, region: str, gr2_path: Path, blend_path: Path):
        self.file_data[tag_type].append(SidecarFileData(utils.relative_path(gr2_path), utils.relative_path(blend_path), permutation, region))
        
    def add_animation_file_data(self, gr2_path: Path, blend_path: Path, name: str, compression: str, animation_type: str, movement: str, space: str, pose_overlay: bool, is_pca: bool):
        data = SidecarFileData(utils.relative_path(gr2_path), utils.relative_path(blend_path))
        data.name = name
        data.compression = compression
        data.animation_type = animation_type
        data.movement = movement
        data.space = space
        data.pose_overlay = pose_overlay
        data.is_pca = is_pca
        self.file_data["animation"].append(data)
                
    def get_child_elements(self):
        for path in self.child_sidecar_paths:
            try:
                tree = ET.parse(path)
                root = tree.getroot()
                content_objects = [element for element in root.findall(".//ContentObject")]
                if self.asset_type in {AssetType.MODEL, AssetType.SKY, AssetType.ANIMATION}:
                    is_animation_only = False
                    anim_only_element = root.find(".//AnimationOnly")
                    if anim_only_element is not None and anim_only_element.text == "True":
                        is_animation_only = True
                        
                    for content_object in content_objects:
                        content_type = content_object.attrib.get("Type")
                        if content_type == "model_animation_graph":
                            self.child_animation_elements.extend([content_network for content_network in content_object.findall(".//ContentNetwork")])
                            continue
                        elif is_animation_only:
                            continue
                        
                        match content_type:
                            case "render_model":
                                self.child_render_elements.extend([content_network for content_network in content_object.findall(".//ContentNetwork")])
                            case "collision_model":
                                self.child_collision_elements.extend([content_network for content_network in content_object.findall(".//ContentNetwork")])
                            case "physics_model":
                                self.child_physics_elements.extend([content_network for content_network in content_object.findall(".//ContentNetwork")])
                
                elif self.asset_type == AssetType.SCENARIO:
                    contents = [element for element in root.findall(".//Content")]
                    for content in contents:
                        content_type = content.attrib.get("Type")
                        if content_type not in {"bsp", "design"}:
                            continue
                        content_name = content.attrib.get("Name")
                        if not content_name:
                            continue
                        
                        for output in content.findall(".//OutputTag"):
                            output.text = str(Path(self.tag_path, content_name))
                            
                        self.child_bsp_elements.append(content)
                        
                elif self.asset_type == AssetType.CINEMATIC:
                    contents = [element for element in root.findall(".//Content")]
                    self.child_scene_elements.extend(contents)
                    
            except:
                utils.print_warning(f"--- Failed to parse {path}")
                
    def write_verification(self):
        m_encoding = "utf-8"
        m_standalone = "yes"
        root = ET.Element("verification")
        
        # COMBAT CROUCH
        mode = ET.SubElement(root, "mode", name="combat, crouch")
        weapon = ET.SubElement(mode, "weapon", name="pistol, unarmed")
        ET.SubElement(weapon, "action", name="idle")
        
        # COMBAT
        mode = ET.SubElement(root, "mode", name="combat")
        weapon = ET.SubElement(mode, "weapon", name="pistol, unarmed")
        ET.SubElement(weapon, "action", name="walk_front")
        ET.SubElement(weapon, "action", name="move_front")
        ET.SubElement(weapon, "action", name="walk_back")
        ET.SubElement(weapon, "action", name="move_back")
        ET.SubElement(weapon, "action", name="walk_left")
        ET.SubElement(weapon, "action", name="move_left")
        ET.SubElement(weapon, "action", name="move_right")
        ET.SubElement(weapon, "action", name="turn_left")
        ET.SubElement(weapon, "action", name="turn_right")
        ET.SubElement(weapon, "action", name="dive_front")
        ET.SubElement(weapon, "action", name="dive_left")
        ET.SubElement(weapon, "action", name="dive_right")
        ET.SubElement(weapon, "action", name="throw_grenade")
        ET.SubElement(weapon, "action", name="airborne")
        ET.SubElement(weapon, "overlay", name="aim_still_up")
        
        dom = xml.dom.minidom.parseString(ET.tostring(root))
        xml_string = dom.toprettyxml(indent="  ")
        part1, part2 = xml_string.split("?>")
        
        verification_path = Path(self.asset_path, f"{self.asset_name}.verification.xml")

        try:
            with open(verification_path, "w") as f:
                f.write(part1 + 'encoding="{}" standalone="{}"?>\n'.format(m_encoding, m_standalone))
                for line in part2.splitlines():
                    if line.strip():
                        f.write(line + "\n")
                        
                self.verification = utils.relative_path(verification_path)
        except:
            utils.print_warning("Failed to write verification xml")
            
    def write_clone(self, clones: dict):
        m_encoding = "utf-8"
        m_standalone = "yes"
        clones_element = ET.Element("Clones")
        for perm, clone_list in clones.items():
            for clone in clone_list:
                clone_element = ET.SubElement(clones_element, "Clone", source=perm, destination=clone.name)
                for override in clone.material_overrides:
                    if not override.enabled:
                        continue
                    
                    if not override.source_material or not override.destination_material:
                        continue
                    
                    source_path = override.source_material.nwo.shader_path
                    destination_path = override.destination_material.nwo.shader_path
                    
                    if not source_path or not destination_path:
                        continue
                    
                    source_path_rel = utils.relative_path(source_path)
                    destination_path_rel = utils.relative_path(destination_path)
                    
                    source_path_full = Path(self.tags_dir, source_path_rel)
                    destination_path_full = Path(self.tags_dir, destination_path_rel)
                    
                    if (not source_path_full.exists() and source_path_full.is_file()) or (not destination_path_full.exists() and destination_path_full.is_file()):
                        continue
                    
                    material_override = ET.SubElement(clone_element, "MaterialOverride")
                    ET.SubElement(material_override, "Original").text=source_path_rel
                    ET.SubElement(material_override, "Override").text=destination_path_rel

        dom = xml.dom.minidom.parseString(ET.tostring(clones_element))
        xml_string = dom.toprettyxml(indent="  ")
        part1, part2 = xml_string.split("?>")
        
        clone_path = Path(self.asset_path, f"{self.asset_name}.clone.xml")

        try:
            with open(clone_path, "w") as f:
                f.write(part1 + 'encoding="{}" standalone="{}"?>\n'.format(m_encoding, m_standalone))
                for line in part2.splitlines():
                    if line.strip():
                        f.write(line + "\n")
                        
                self.clone = utils.relative_path(clone_path)
        except:
            utils.print_warning("Failed to write clone xml")
        
    def build(self, actor_render_model_path=None):
        m_encoding = "utf-8"
        m_standalone = "yes"
        metadata = ET.Element("Metadata")
        self._write_header(metadata)
        if actor_render_model_path is not None:
            self._get_object_output_types(metadata, "model", for_actor=True)
        else:
            match self.asset_type:
                case AssetType.MODEL:
                    self._get_object_output_types(metadata, "model", self._get_model_tags())
                case AssetType.SCENARIO:
                    self._get_object_output_types(metadata, "scenario")
                case AssetType.SKY:
                    self._get_object_output_types(metadata, "model" if self.corinth else "sky")
                case AssetType.DECORATOR_SET:
                    self._get_object_output_types(metadata, "decorator_set", "decorator_set")
                case AssetType.PARTICLE_MODEL:
                    self._get_object_output_types(metadata, "particle_model", "particle_model")
                case AssetType.PREFAB:
                    self._get_object_output_types(metadata, "prefab", "prefab")
                case AssetType.ANIMATION:
                    self._get_object_output_types(metadata, "model")
                case AssetType.CINEMATIC:
                    self._get_object_output_types(metadata, "cinematic")

        # self._write_folders(metadata)
        self._write_face_collections(metadata)
        
        if actor_render_model_path is not None:
            self._write_actor_contents(metadata, actor_render_model_path)
        else:
            match self.asset_type:
                case AssetType.MODEL:
                    self._write_model_contents(metadata)
                case AssetType.SCENARIO:
                    self._write_scenario_contents(metadata)
                case AssetType.SKY:
                    self._write_sky_contents(metadata)
                case AssetType.DECORATOR_SET:
                    self._write_decorator_contents(metadata)
                case AssetType.PARTICLE_MODEL:
                    self._write_particle_contents(metadata)
                case AssetType.PREFAB:
                    self._write_prefab_contents(metadata)
                case AssetType.ANIMATION:
                    self._write_animation_contents(metadata)
                case AssetType.CINEMATIC:
                    for cin_scene in self.cinematic_scenes:
                        self._write_cinematic_contents(metadata, cin_scene)

        dom = xml.dom.minidom.parseString(ET.tostring(metadata))
        xml_string = dom.toprettyxml(indent="  ")
        part1, part2 = xml_string.split("?>")

        if Path(self.sidecar_path_full).exists():
            if not os.access(self.sidecar_path_full, os.W_OK):
                raise RuntimeError(f"Sidecar is read only, cannot complete export: {self.sidecar_path_full}\n")
        
        with open(self.sidecar_path_full, "w") as f:
            f.write(part1 + 'encoding="{}" standalone="{}"?>\n'.format(m_encoding, m_standalone))
            for line in part2.splitlines():
                if line.strip():
                    f.write(line + "\n")

    def _write_header(self, metadata):
        header = ET.SubElement(metadata, "Header")
        ET.SubElement(header, "MainRev").text = "0"
        ET.SubElement(header, "PointRev").text = "6"
        ET.SubElement(header, "Description").text = "Forged in Foundry"
        ET.SubElement(header, "Created").text = datetime.today().strftime("%Y-%m-%d %H:%M:%S")
        ET.SubElement(header, "By").text = getuser()
        ET.SubElement(header, "DirectoryType").text = "TAE.Shared.NWOAssetDirectory"
        ET.SubElement(header, "Schema").text = "1"
        ET.SubElement(header, "SourceBlend").text = self.relative_blend
        ET.SubElement(header, "BlenderVersion").text = bpy.app.version_string
        ET.SubElement(header, "FoundryVersion").text = utils.get_version_string()
        ET.SubElement(header, "AnimationOnly").text = str(self.asset_type == AssetType.ANIMATION)

    def _get_model_tags(self):
        tags = ["model"]
        
        if self.asset_type == AssetType.ANIMATION:
            tags.append("scenery")
            self.no_top_level_tag = True
            return tags
        elif self.asset_type == AssetType.SKY:
            tags.append("scenery")
            return tags
        
        if self.scene_settings.output_biped:
            tags.append("biped")
        if self.scene_settings.output_crate:
            tags.append("crate")
        if self.scene_settings.output_creature:
            tags.append("creature")
        if self.scene_settings.output_device_control:
            tags.append("device_control")
        if self.scene_settings.output_device_dispenser:
            tags.append("device_dispenser")
        if self.scene_settings.output_device_machine:
            tags.append("device_machine")
        if self.scene_settings.output_device_terminal:
            tags.append("device_terminal")
        if self.scene_settings.output_effect_scenery:
            tags.append("effect_scenery")
        if self.scene_settings.output_equipment:
            tags.append("equipment")
        if self.scene_settings.output_giant:
            tags.append("giant")
        if self.scene_settings.output_scenery:
            tags.append("scenery")
        if self.scene_settings.output_vehicle:
            tags.append("vehicle")
        if self.scene_settings.output_weapon:
            tags.append("weapon")
        if len(tags) == 1:
            # Must have high level tag, but we can delete this post export
            tags.append("scenery")
            self.no_top_level_tag = True

        return tags

    def _get_object_output_types(self, metadata, sidecar_type, output_tags=[], for_actor=False):
        if sidecar_type == "sky":
            asset = ET.SubElement(metadata, "Asset", Name=self.asset_name, Type=sidecar_type, Sky="true")
        else:
            asset = ET.SubElement(metadata, "Asset", Name=self.asset_name, Type=sidecar_type)
            
        tagcollection = ET.SubElement(asset, "OutputTagCollection")
        
        if for_actor:
            ET.SubElement(tagcollection, "OutputTag", Type="model").text = self.tag_path
            ET.SubElement(tagcollection, "OutputTag", Type="scenery").text = self.tag_path
        else:
            match self.asset_type:
                case AssetType.MODEL:
                # models are the only sidecar type with optional high level tags exports, all others are fixed
                    for tag in output_tags:
                        ET.SubElement(tagcollection, "OutputTag", Type=tag).text = self.tag_path
                case AssetType.SCENARIO:
                    ET.SubElement(tagcollection, "OutputTag", Type="scenario_lightmap").text = f"{self.tag_path}_faux_lightmap"
                    ET.SubElement(tagcollection, "OutputTag", Type="structure_seams").text = self.tag_path
                    ET.SubElement(tagcollection, "OutputTag", Type="scenario").text = self.tag_path

                case AssetType.DECORATOR_SET:
                    ET.SubElement(tagcollection, "OutputTag", Type="decorator_set").text = self.tag_path

                case AssetType.PARTICLE_MODEL:
                    ET.SubElement(tagcollection, "OutputTag", Type="particle_model").text = self.tag_path

                case AssetType.PREFAB:
                    ET.SubElement(tagcollection, "OutputTag", Type="prefab").text = self.tag_path

                case AssetType.SKY | AssetType.ANIMATION:
                    ET.SubElement(tagcollection, "OutputTag", Type="model").text = self.tag_path
                    ET.SubElement(tagcollection, "OutputTag", Type="scenery").text = self.tag_path
                    
                case AssetType.CINEMATIC:
                    # if not self.corinth:
                    #     ET.SubElement(tagcollection, "OutputTag", Type="model").text = self.tag_path
                    ET.SubElement(tagcollection, "OutputTag", Type="cinematic").text = self.tag_path

    def _write_folders(self, metadata):
        folders = ET.SubElement(metadata, "Folders")

        ET.SubElement(folders, "Reference").text = "\\reference"
        ET.SubElement(folders, "Temp").text = "\\temp"
        ET.SubElement(folders, "SourceModels").text = "\\models\\work"
        ET.SubElement(folders, "GameModels").text = "\\models"
        ET.SubElement(folders, "GamePhysicsModels").text = "\\models"
        ET.SubElement(folders, "GameCollisionModels").text = "\\models"
        ET.SubElement(folders, "ExportModels").text = "\\export\\models"
        ET.SubElement(folders, "ExportPhysicsModels").text = "\\export\\models"
        ET.SubElement(folders, "ExportCollisionModels").text = "\\export\\models"
        ET.SubElement(folders, "SourceAnimations").text = "\\animations\\work"
        ET.SubElement(folders, "AnimationsRigs").text = "\\animations\\rigs"
        ET.SubElement(folders, "GameAnimations").text = "\\animations"
        ET.SubElement(folders, "ExportAnimations").text = "\\export\\animations"
        ET.SubElement(folders, "SourceBitmaps").text = "\\bitmaps"
        ET.SubElement(folders, "GameBitmaps").text = "\\bitmaps"
        ET.SubElement(folders, "CinemaSource").text = "\\cinematics"
        ET.SubElement(folders, "CinemaExport").text = "\\export\\cinematics"
        ET.SubElement(folders, "ExportBSPs").text = "\\models"
        ET.SubElement(folders, "SourceBSPs").text = "\\models"
        ET.SubElement(folders, "RigFlags").text = "\\animations\\rigs\\flags"
        ET.SubElement(folders, "RigPoses").text = "\\animations\\rigs\\poses"
        ET.SubElement(folders, "RigRenders").text = "\\animations\\rigs\\render"
        ET.SubElement(folders, "Scripts").text = "\\scripts"
        ET.SubElement(folders, "FacePoses").text = "\\animations\\rigs\\poses\\face_poses"
        ET.SubElement(folders, "CinematicOutsource").text = "\\outsource"

        if not self.corinth:
            ET.SubElement(folders, "Retarget").text = "\\working\\retarget"
            ET.SubElement(folders, "RetargetSourceAnimations").text = "\\working\\retarget\\binge"
            ET.SubElement(folders, "RetargetTargetAnimations").text = "\\working\\retarget\\purge"
            ET.SubElement(folders, "Export").text = "\\export"
            ET.SubElement(folders, "CinematicSceneSegments").text = "\\segments"
            ET.SubElement(folders, "SourceAnimationLibrary").text = "\\animations\\library"

    def _write_face_collections(self, metadata):  
        # FaceCollections is where regions and global materials enums are defined
        faceCollections = ET.SubElement(metadata, "FaceCollections")
        
        if self.asset_type in {AssetType.MODEL, AssetType.SKY}:
            f1 = ET.SubElement(faceCollections, "FaceCollection", Name="regions", StringTable="connected_geometry_regions_table", Description="Model regions")
            face_collection_entries = ET.SubElement(f1, "FaceCollectionEntries")
            for idx, region in enumerate(self.regions):
                ET.SubElement(face_collection_entries, "FaceCollectionEntry", Index=str(idx), Name=region, Active=self._region_active_state(region))

        if self.asset_type in {AssetType.MODEL, AssetType.SCENARIO, AssetType.PREFAB}:
            f2 = ET.SubElement(faceCollections, "FaceCollection", Name="global materials override", StringTable="connected_geometry_global_material_table", Description="Global material overrides")

            FaceCollectionsEntries2 = ET.SubElement(f2, "FaceCollectionEntries")
            for idx, global_material in enumerate(self.global_materials):
                ET.SubElement(FaceCollectionsEntries2,"FaceCollectionEntry", Index=str(idx), Name=global_material, Active="true")

    def _write_network_files(self, content_object, file_data: SidecarFileData):
        network = ET.SubElement(content_object, "ContentNetwork", Name=file_data.permutation, Type="")
        ET.SubElement(network, "InputFile").text = file_data.blend_path
        ET.SubElement(network, "IntermediateFile").text = file_data.gr2_path
        
        return network.attrib["Name"]

    def _write_model_contents(self, metadata):
        if self.verification is None:
            contents = ET.SubElement(metadata, "Contents")
        else:
            contents = ET.SubElement(metadata, "Contents", VerifyAnimation=self.verification)
            
        if self.clone is None:
            content = ET.SubElement(contents, "Content", Name=self.asset_name, VerifyAnimation="", Type="model")
        else:
            content = ET.SubElement(contents, "Content", Name=self.asset_name, PermutationClones=self.clone, Type="model")
            
        ##### RENDER #####
        render_data = self.file_data.get("render")
        if render_data or self.child_render_elements:
            network_names = set()
            content_object = ET.SubElement(content, "ContentObject", Name="", Type="render_model")
            if render_data is not None:
                for data in render_data:
                    network_names.add(self._write_network_files(content_object, data))
            
            for element in self.child_render_elements:
                if element.attrib.get("Name") not in network_names:
                    content_object.append(element)

            output = ET.SubElement(content_object, "OutputTagCollection")
            ET.SubElement(output, "OutputTag", Type="render_model").text = self.tag_path

        ##### PHYSICS #####
        physics_data = self.file_data.get("physics")
        if physics_data or self.child_physics_elements:
            network_names = set()
            content_object = ET.SubElement(content, "ContentObject", Name="", Type="physics_model")
            if physics_data is not None:
                for data in physics_data:
                    network_names.add(self._write_network_files(content_object, data))
                
            for element in self.child_physics_elements:
                if element.attrib.get("Name") not in network_names:
                    content_object.append(element)

            output = ET.SubElement(content_object, "OutputTagCollection")
            ET.SubElement(output, "OutputTag", Type="physics_model").text = self.tag_path

        ##### COLLISION #####
        collision_data = self.file_data.get("collision")
        if collision_data or self.child_collision_elements:
            network_names = set()
            content_object = ET.SubElement(content, "ContentObject", Name="", Type="collision_model")
            if collision_data is not None:
                for data in collision_data:
                    network_names.add(self._write_network_files(content_object, data))
                
            for element in self.child_collision_elements:
                if element.attrib.get("Name") not in network_names:
                    content_object.append(element)

            output = ET.SubElement(content_object, "OutputTagCollection")
            ET.SubElement(output, "OutputTag", Type="collision_model").text = self.tag_path

        ##### SKELETON #####
        if self.has_armature:
            self._write_skeleton_content(content)

        ##### MARKERS #####
        markers_data = self.file_data.get("markers")
        if markers_data:
            content_object = ET.SubElement(content, "ContentObject", Name="", Type="markers")
            self._write_network_files(content_object, markers_data[0])
            ET.SubElement(content_object, "OutputTagCollection")

        ##### ANIMATIONS #####
        if self.has_armature:
            self._write_animation_content(content)

    def _write_network_files_bsp(self, content_object, file_data: SidecarFileData, shared=False, design=False):
        network = ET.SubElement(content_object, "ContentNetwork", Name=f'{self.asset_name}_{"design" if design else "structure"}_{file_data.region}_{file_data.permutation}', Type="")
        if shared:
            network.attrib["Name"] += "_shared"
        ET.SubElement(network, "InputFile").text = file_data.blend_path
        ET.SubElement(network, "IntermediateFile").text = file_data.gr2_path
        
        return network.attrib["Name"]

    def _write_scenario_contents(self, metadata):
        contents = ET.SubElement(metadata, "Contents")
        ##### STRUCTURE #####
        shared_data = self.file_data.get("shared")
        bsp_data = self.file_data.get("structure")
        this_contents = {}
        network_names = set()
        for bsp in self.structure:
            content_name = bsp
            content = ET.SubElement(contents, "Content", Name=content_name, Type="bsp")
            this_contents[content_name] = content
            content_object = ET.SubElement(content, "ContentObject", Name="", Type="scenario_structure_bsp")
            bsp_data = self.file_data.get("structure")
            if not bsp_data:
                continue
            for data in bsp_data:
                if data.region == bsp:
                    network_names.add(self._write_network_files_bsp(content_object, data))
            if shared_data:
                for data in shared_data:
                    network_names.add(self._write_network_files_bsp(content_object, data, True))

            output = ET.SubElement(content_object, "OutputTagCollection")
            ET.SubElement(output, "OutputTag", Type="scenario_structure_bsp").text = f"{self.relative_asset_path}\\{content_name}"
            ET.SubElement(output, "OutputTag", Type="scenario_structure_lighting_info").text = f"{self.relative_asset_path}\\{content_name}"

        ##### STRUCTURE DESIGN #####
        for bsp in self.design:
            design_data = self.file_data.get("design")
            content_name = bsp
            content = ET.SubElement(contents, "Content", Name=content_name, Type="design")
            this_contents[content_name] = content
            content_object = ET.SubElement(content, "ContentObject", Name="", Type="structure_design")

            if not design_data: continue
            for data in design_data:
                if data.region == bsp:
                    network_names.add(self._write_network_files_bsp(content_object, data, design=True))

            output = ET.SubElement(content_object, "OutputTagCollection")
            ET.SubElement(output, "OutputTag", Type="structure_design").text = f"{self.relative_asset_path}\\{content_name}"
            
        for bsp_content in self.child_bsp_elements:
            existing_bsp_content = this_contents.get(bsp_content.attrib.get("Name"))
            if existing_bsp_content is None:
                contents.append(bsp_content)
            else:
                existing_bsp_content_object = existing_bsp_content.find(".//ContentObject")
                if existing_bsp_content_object:
                    for element in bsp_content.findall(".//ContentNetwork"):
                        if element.attrib.get("Name") not in network_names:
                            existing_bsp_content_object.append(element)
                            # existing_bsp_content_object.insert(len(existing_bsp_content_object) - 2, element)

    def _write_sky_contents(self, metadata):
        contents = ET.SubElement(metadata, "Contents")
        if self.clone is None:
            content = ET.SubElement(contents, "Content", Name=self.asset_name, Type="model")
        else:
            content = ET.SubElement(contents, "Content", Name=self.asset_name, PermutationClones=self.clone, Type="model")
        render_data = self.file_data.get("render")
        if render_data or self.child_render_elements:
            content_object = ET.SubElement(content, "ContentObject", Name="", Type="render_model")
            network_names = set()
            if render_data is not None:
                for data in render_data:
                    network_names.add(self._write_network_files(content_object, data))
                
            for element in self.child_render_elements:
                if element.attrib.get("Name") not in network_names:
                    content_object.append(element)
                
            output = ET.SubElement(content_object, "OutputTagCollection")
            ET.SubElement(output, "OutputTag", Type="render_model").text = self.tag_path

        if self.has_armature:
            self._write_skeleton_content(content)
        
        ##### MARKERS #####
        markers_data = self.file_data.get("markers")
        if markers_data:
            content_object = ET.SubElement(content, "ContentObject", Name="", Type="markers")
            self._write_network_files(content_object, markers_data[0])
            ET.SubElement(content_object, "OutputTagCollection")

    def _write_decorator_contents(self, metadata):
        contents = ET.SubElement(metadata, "Contents")
        content = ET.SubElement(contents, "Content", Name=self.asset_name, Type="decorator_set")
        render_data = self.file_data.get("render")
        if render_data:
            ordered_lods = sorted(self.lods)
            for lod in ordered_lods:
                lod_str = str(lod - 1)
                content_object = ET.SubElement(content, "ContentObject", Name=lod_str, Type="render_model", LOD=lod_str)
                for data in render_data:
                    self._write_network_files(content_object, data)

                output = ET.SubElement(content_object, "OutputTagCollection")
                ET.SubElement(output, "OutputTag", Type="render_model").text = f"{self.tag_path}_lod{lod}"

    def _write_particle_contents(self, metadata):
        contents = ET.SubElement(metadata, "Contents")
        content = ET.SubElement(contents, "Content", Name=self.asset_name, Type="particle_model")

        render_data = self.file_data.get("render")
        if render_data:
            content_object = ET.SubElement(content, "ContentObject", Name="", Type="particle_model")
            for data in render_data:
                self._write_network_files(content_object, data)

            output = ET.SubElement(content_object, "OutputTagCollection")
            if self.nwo.particle_uses_custom_points:
                ET.SubElement(output, "OutputTag", Type="particle_emitter_custom_points").text = self.tag_path

    def _write_prefab_contents(self, metadata):
        contents = ET.SubElement(metadata, "Contents")
        content = ET.SubElement(contents, "Content", Name=self.asset_name, Type="prefab")
        bsp_data = self.file_data.get("structure")
        if bsp_data:
            content_object = ET.SubElement(content, "ContentObject", Name="", Type="scenario_structure_bsp")
            for data in bsp_data:
                self._write_network_files_bsp(content_object, data)

            output = ET.SubElement(content_object, "OutputTagCollection")
            ET.SubElement(output, "OutputTag", Type="scenario_structure_bsp").text = self.tag_path
            ET.SubElement(output, "OutputTag", Type="scenario_structure_lighting_info").text = self.tag_path

    def _write_animation_contents(self, metadata):
        # NULL RENDER
        contents = ET.SubElement(metadata, "Contents")
        content = ET.SubElement(contents, "Content", Name=self.asset_name, Type="model")
        content_object = ET.SubElement(content, "ContentObject", Name="", Type="render_model")
        render_data = self.file_data.get("render")
        for data in render_data:
            self._write_network_files(content_object, data)

        output = ET.SubElement(content_object, "OutputTagCollection")
        ET.SubElement(output, "OutputTag", Type="render_model").text = self.tag_path

        ##### SKELETON #####
        self._write_skeleton_content(content)

        ##### ANIMATIONS #####
        self._write_animation_content(content)
        
    def _write_actor_contents(self, metadata, actor_render_model_path):
        contents = ET.SubElement(metadata, "Contents")
        content = ET.SubElement(contents, "Content", Name=self.asset_name, Type="model")
        content_object = ET.SubElement(content, "ContentObject", Name="", Type="render_model")
        self._write_network_files(content_object, SidecarFileData(str(Path(Path(self.relative_asset_path).parent, f"{self.asset_name}_render.gr2")), utils.relative_path(bpy.data.filepath)))
        output = ET.SubElement(content_object, "OutputTagCollection")
        ET.SubElement(output, "OutputTag", Type="render_model").text = actor_render_model_path
        content_object = ET.SubElement(content, "ContentObject", Name="", Type="skeleton")
        self._write_network_files(content_object, SidecarFileData(str(Path(Path(self.relative_asset_path).parent, f"{self.asset_name}_skeleton.gr2")), utils.relative_path(bpy.data.filepath)))
        # ET.SubElement(content_object, "OutputTagCollection")

    def _write_skeleton_content(self, content):
        skeleton_data = self.file_data.get("skeleton")
        if skeleton_data:
            content_object = ET.SubElement(content, "ContentObject", Name="", Type="skeleton")
            self._write_network_files(content_object, skeleton_data[0])
            ET.SubElement(content_object, "OutputTagCollection")
        

    def _write_animation_content(self, content):
        animation_data = self.file_data.get("animation")
        if animation_data or self.child_animation_elements:
            content_object = ET.SubElement(content, "ContentObject", Name="", Type="model_animation_graph")
            if animation_data is not None:
                for data in animation_data:
                    compression = data.compression if data.compression != "Default" else None
                    network_attribs = {"Name": data.name, "Type": "Base"}
                    if data.animation_type == 'overlay':
                        network_attribs['Type'] = "Overlay"
                        network_attribs['ModelAnimationOverlayBlending'] = "Additive"
                        if data.pose_overlay:
                            network_attribs['ModelAnimationOverlayType'] = "Pose"
                            self.pose_overlays.add(data.name.replace(' ', ':'))
                        else:
                            network_attribs['ModelAnimationOverlayType'] = "Keyframe"
                    elif data.animation_type == 'world' and is_corinth():
                        network_attribs['Type'] = "World"
                        network_attribs['ModelAnimationMovementData'] = "XYZAbsolute"
                    elif data.animation_type == 'replacement':
                        network_attribs['Type'] = "Overlay"
                        network_attribs['ModelAnimationOverlayType'] = "Keyframe"
                        if data.space == 'object':
                            network_attribs['ModelAnimationOverlayBlending'] = "ReplacementObjectSpace"
                        else:
                            network_attribs['ModelAnimationOverlayBlending'] = "ReplacementLocalSpace"
                    else:
                        match data.movement:
                            case 'world':
                                self.reach_world_animations.add(data.name.replace(' ', ':'))
                            case 'none':
                                network_attribs['ModelAnimationMovementData'] = "None"
                            case 'xy':
                                network_attribs['ModelAnimationMovementData'] = "XY"
                            case 'xyyaw':
                                network_attribs['ModelAnimationMovementData'] = "XYYaw"
                            case 'xyzyaw':
                                network_attribs['ModelAnimationMovementData'] = "XYZYaw"
                            case _:
                                network_attribs['ModelAnimationMovementData'] = "XYZFullRotation"
                        
                    if compression is not None:
                        network_attribs['Compression'] = compression
                    
                    if self.corinth and data.is_pca:
                        network_attribs["PCA"] = "True"

                    network = ET.SubElement(content_object, "ContentNetwork", network_attribs)

                    ET.SubElement(network, "InputFile").text = data.blend_path
                    ET.SubElement(network, "IntermediateFile").text = data.gr2_path

            for animation in self.scene_settings.animations:
                if not animation.export_this:
                    continue

                renames = animation.animation_renames
                for rename in renames:
                    ET.SubElement(
                        content_object,
                        "ContentNetwork",
                        Name=rename.name,
                        Type="Rename",
                        NetworkReference=animation.name,
                    )
                    
            for item in self.scene_settings.animation_copies:
                ET.SubElement(
                    content_object,
                    "ContentNetwork",
                    Name=item.name,
                    Type="Copy",
                    NetworkReference=item.source_name,
                )

            for item in self.animation_composites:
                ET.SubElement(
                    content_object,
                    "ContentNetwork",
                    Name=item.name,
                    Type="CompositeOverlay" if item.overlay else "Composite",
                    NetworkReference=write_composite_xml(item),
                )
                
            for element in self.child_animation_elements:
                content_object.append(element)
                
            output = ET.SubElement(content_object, "OutputTagCollection")
            ET.SubElement(output, "OutputTag", Type="frame_event_list").text = self.tag_path
            if self.corinth:
                ET.SubElement(output, "OutputTag", Type="pca_animation").text = self.tag_path
                
            ET.SubElement(output, "OutputTag", Type="model_animation_graph").text = self.tag_path
        
        # else:
        #     if not self.scene_settings.template_model_animation_graph and (self.scene_settings.output_scenery or self.scene_settings.output_biped or self.scene_settings.output_vehicle or self.scene_settings.output_giant):
        #         content_object = ET.SubElement(content, "ContentObject", Name="", Type="model_animation_graph")
        #         output = ET.SubElement(content_object, "OutputTagCollection")
        #         ET.SubElement(output, "OutputTag", Type="model_animation_graph").text = self.tag_path
                
            for path in self.child_sidecar_paths:
                self.append_animation_content_from_file(path, content)

    def _region_active_state(self, region_name):
        region = self.nwo.regions_table[region_name]
        return 'true' if region.active else 'false'
    
    def _write_cinematic_contents(self, metadata, cin_scene):
        contents = ET.SubElement(metadata, "Contents")
        content = ET.SubElement(contents, "Content", Name=cin_scene.name, Type="scene")
        
        # sound_sequences = [sequence for sequence in self.context.scene.sequence_editor.strips if sequence.type == 'SOUND']
        # audio_content_object = ET.SubElement(content, "ContentObject", Name="", Type="cinematic_audio")
        # for sequence in sound_sequences:
        #     sound = sequence.sound
        #     filepath = Path(sound.filepath)
        #     if filepath.is_absolute() and filepath.is_relative_to(self.data_dir):
        #         relative = Path(utils.relative_path(filepath))
        #         sound_name = relative.with_suffix("").name
        #         tag_path = Path(self.relative_asset_path, "dialog", f"{sound_name}.sound")
        #         network = ET.SubElement(audio_content_object, "ContentNetwork", Name=sound_name, Type="", Target="spartans", StartFrame=str(int(sequence.frame_start)), SoundTagFile=r"foundry\cinematic_test\kat_sniped\test.aif", DialogColor="NONE")
        #         ET.SubElement(network, "InputFile").text = str(relative)
        #     else:
        #         utils.print_warning(f"Cannot add audio file because it is not saved to the project data folder: {filepath}")
        # ET.SubElement(audio_content_object, "OutputTagCollection")
        
        # QUA
        if not self.corinth:
            scene_content_object = ET.SubElement(content, "ContentObject", Name="", Type="cinematic_scene")
            network = ET.SubElement(scene_content_object, "ContentNetwork", Name="", Type="")
            ET.SubElement(network, "InputFile").text = self.relative_blend
            ET.SubElement(network, "IntermediateFile").text = self.relative_blend
            collection = ET.SubElement(scene_content_object, "OutputTagCollection")
            ET.SubElement(collection, "OutputTag", Type="cinematic_scene").text = str(cin_scene.path_no_ext)
        
        # Shots
        shots_content_object = ET.SubElement(content, "ContentObject", Name="", Type="cinematic_shots") # Sequencer="True"
        for shot in cin_scene.shots:
            ET.SubElement(shots_content_object, "ContentNetwork", Name=str(shot.shot_index + 1), Type="", StartFrame=str(shot.frame_start), EndFrame=str(shot.frame_end))
        
        # Animations
        for actor, animations in cin_scene.actor_animations.items():
            actor_content_object = ET.SubElement(content, "ContentObject", Name=actor.name, Type="model_animation_graph", Sidecar=actor.sidecar)
            for animation in animations:
                network = ET.SubElement(actor_content_object, "ContentNetwork", Name=animation.name, Type="Base", ShotId=str(animation.shot_index + 1), ModelAnimationMovementData="None")
                if self.corinth:
                    network.attrib["PCA"] = str(animation.is_pca).capitalize()
                ET.SubElement(network, "IntermediateFile").text = animation.gr2_path
            collection = ET.SubElement(actor_content_object, "OutputTagCollection")
            ET.SubElement(collection, "OutputTag", Type="model_animation_graph").text = utils.dot_partition(actor.graph)
            
        contents.extend(self.child_scene_elements)
    
def write_composite_xml(composite) -> str:
    composite_xml = CompositeXML(composite)
    return composite_xml.build_xml()

def get_cinematic_scenes(filepath: Path | str) -> list[str] | None:
    """Opens the specified sidecar and gets a list of all cinematic scenes"""
    scene_names = []
    try:
        tree = ET.parse(filepath)
        root = tree.getroot()
        contents = [element for element in root.findall(".//Content")]
        for content in contents:
            content_type = content.attrib.get("Type")
            if content_type == "scene":
                name = content.attrib.get("Name")
                if name is not None:
                    scene_names.append(name)
    finally:
        return scene_names