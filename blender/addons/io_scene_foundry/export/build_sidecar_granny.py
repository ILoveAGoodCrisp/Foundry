from collections import defaultdict
from datetime import datetime
from getpass import getuser
import os
from pathlib import Path
import bpy
import xml.etree.cElementTree as ET
import xml.dom.minidom

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
    
    def __init__(self, gr2_path: Path, blend_path: Path, permutation: str = "default", region: str = "default"):
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
        

class Sidecar:
    def __init__(self, sidecar_path_full: Path, sidecar_path: Path, asset_path: Path, asset_name: str, asset_type: AssetType, scene_settings: NWO_ScenePropertiesGroup, corinth: bool, context: bpy.types.Context):
        self.reach_world_animations = set()
        self.pose_overlays = set()
        self.tag_path = relative_path(Path(asset_path, asset_name))
        self.asset_path = asset_path
        self.asset_name = asset_name
        self.asset_type = asset_type
        self.sidecar_path = sidecar_path
        self.sidecar_path_full = sidecar_path_full
        self.relative_blend = str(Path(bpy.data.filepath).relative_to(get_data_path()))
        self.external_blend = self.relative_blend == bpy.data.filepath
        self.scene_settings = scene_settings
        self.corinth = corinth
        self.context = context
        self.lods = []
        
        self.structure = set()
        self.design = set()
        self.has_armature = False
        self.regions = []
        self.global_materials = []
        self.file_data: dict[list[SidecarFileData]] = defaultdict(list)
        
    def add_file_data(self, tag_type: str, permutation: str, region: str, gr2_path: Path, blend_path: Path):
        self.file_data[tag_type].append(SidecarFileData(utils.relative_path(gr2_path), utils.relative_path(blend_path), permutation, region))
        
    def add_animation_file_data(self, gr2_path: Path, blend_path: Path, name: str, compression: str, animation_type: str, movement: str, space: str, pose_overlay: bool):
        data = SidecarFileData(utils.relative_path(gr2_path), utils.relative_path(blend_path))
        data.name = name
        data.compression = compression
        data.animation_type = animation_type
        data.movement = movement
        data.space = space
        data.pose_overlay = pose_overlay
        self.file_data["animation"].append(data)

    def build(self):
        m_encoding = "utf-8"
        m_standalone = "yes"
        metadata = ET.Element("Metadata")
        self._write_header(metadata)
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
                self.get_object_output_types(metadata, "particle_model", "particle_model")
            case AssetType.PREFAB:
                self.get_object_output_types(metadata, "prefab", "prefab")
            case AssetType.ANIMATION:
                self.get_object_output_types(metadata, "model")

        self._write_folders(metadata)
        self._write_face_collections(metadata)

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

        dom = xml.dom.minidom.parseString(ET.tostring(metadata))
        xml_string = dom.toprettyxml(indent="  ")
        part1, part2 = xml_string.split("?>")

        if Path(self.sidecar_path_full).exists():
            if not os.access(self.sidecar_path_full, os.W_OK):
                raise RuntimeError(f"Sidecar is read only, cannot complete export: {self.sidecar_path_full}\n")
        
        with open(self.sidecar_path_full, "w") as xfile:
            xfile.write(
                part1
                + 'encoding="{}" standalone="{}"?>'.format(m_encoding, m_standalone)
                + part2
            )

    def _write_header(self, metadata):
        header = ET.SubElement(metadata, "Header")
        ET.SubElement(header, "MainRev").text = "0"
        ET.SubElement(header, "PointRev").text = "6"
        ET.SubElement(header, "Description").text = "Forged in Foundry"
        ET.SubElement(header, "Created").text = str(datetime.today().strftime("%Y-%m-%d %H:%M:%S"))
        ET.SubElement(header, "By").text = getuser()
        ET.SubElement(header, "SourceBlend").text = self.relative_blend
        ET.SubElement(header, "DirectoryType").text = "TAE.Shared.NWOAssetDirectory"
        ET.SubElement(header, "Schema").text = "1"

    def _get_model_tags(self):
        tags = ["model"]
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

    def _get_object_output_types(self, metadata, sidecar_type, output_tags=[]):
        if sidecar_type == "sky":
            asset = ET.SubElement(metadata, "Asset", Name=self.asset_name, Type=sidecar_type, Sky="true")
        else:
            asset = ET.SubElement(metadata, "Asset", Name=self.asset_name, Type=sidecar_type)
            
        tagcollection = ET.SubElement(asset, "OutputTagCollection")

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

    def _write_model_contents(self, metadata):
        contents = ET.SubElement(metadata, "Contents")
        content = ET.SubElement(contents, "Content", Name=self.asset_name, Type="model")
        ##### RENDER #####
        content_object = ET.SubElement(content, "ContentObject", Name="", Type="render_model")
        render_data = self.file_data.get("render")
        for data in render_data:
            self._write_network_files(content_object, data)

        output = ET.SubElement(content_object, "OutputTagCollection")
        ET.SubElement(output, "OutputTag", Type="render_model").text = self.tag_path

        ##### PHYSICS #####
        physics_data = self.file_data.get("physics")
        if physics_data:
            content_object = ET.SubElement(content, "ContentObject", Name="", Type="physics_model")
            for data in physics_data:
                self._write_network_files(content_object, data)

            output = ET.SubElement(content_object, "OutputTagCollection")
            ET.SubElement(output, "OutputTag", Type="physics_model").text = self.tag_path

        ##### COLLISION #####
        collision_data = self.file_data.get("collision")
        if collision_data:
            content_object = ET.SubElement(content, "ContentObject", Name="", Type="collision_model")
            for data in collision_data:
                self._write_network_files(content_object, data)

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

    def _write_network_files_bsp(self, content_object, file_data: SidecarFileData, shared=False):
        if file_data.permutation == 'default':
            network = ET.SubElement(content_object, "ContentNetwork", Name=f'{self.asset_name}_{file_data.region}', Type="")
        else:
            network = ET.SubElement(content_object, "ContentNetwork", Name=f'{self.asset_name}_{file_data.region}_{file_data.permutation}', Type="")
        if shared:
            network.attrib["Name"] += "_shared"
        ET.SubElement(network, "InputFile").text = file_data.blend_path
        ET.SubElement(network, "IntermediateFile").text = file_data.gr2_path

    def _write_scenario_contents(self, metadata):
        contents = ET.SubElement(metadata, "Contents")
        ##### STRUCTURE #####
        shared_data = self.file_data.get("shared")
        for bsp in self.structure:
            content = ET.SubElement(contents, "Content", Name=f"{self.asset_name}_{bsp}", Type="bsp")
            content_object = ET.SubElement(content, "ContentObject", Name="", Type="scenario_structure_bsp")
            bsp_data = self.file_data.get("structure")
            for data in bsp_data:
                self._write_network_files_bsp(content_object, data)
            if shared_data:
                for data in shared_data:
                    self._write_network_files_bsp(content_object, data, True)

            output = ET.SubElement(content_object, "OutputTagCollection")
            ET.SubElement(output, "OutputTag", Type="scenario_structure_bsp").text = f"{self.tag_path}_{bsp}"
            ET.SubElement(output, "OutputTag", Type="scenario_structure_lighting_info").text = f"{self.tag_path}_{bsp}"

        ##### STRUCTURE DESIGN #####
        for bsp in self.design:
            design_data = self.file_data.get("design")
            content = ET.SubElement(contents, "Content", Name=f"{self.asset_name}_{bsp}_structure_design", Type="design")
            content_object = ET.SubElement(content, "ContentObject", Name="", Type="structure_design")

            if not design_data: continue
            for data in design_data:
                self._write_network_files_bsp(content_object, data)

            output = ET.SubElement(content_object, "OutputTagCollection")
            ET.SubElement(output, "OutputTag", Type="structure_design").text = f"{self.tag_path}_{bsp}_structure_design"

    def _write_sky_contents(self, metadata):
        contents = ET.SubElement(metadata, "Contents")
        content = ET.SubElement(contents, "Content", Name=self.asset_name, Type="model")
        content_object = ET.SubElement(content, "ContentObject", Name="", Type="render_model")

        render_data = self.file_data.get("render")
        for data in render_data:
            self._write_network_files(content_object, data)
            
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
            for lod in self.lods:
                lod_str = str(lod - 1)
                content_object = ET.SubElement(content, "ContentObject", Name=lod_str, Type="render_model", LOD=lod_str)
                for data in render_data:
                    self._write_network_files(content_object, data)

                output = ET.SubElement(content_object, "OutputTagCollection")
                ET.SubElement(output, "OutputTag", Type="render_model").text = f"{self.tag_path}_lod{lod}"

    def _write_particle_contents(self, metadata, sidecar_paths):
        contents = ET.SubElement(metadata, "Contents")
        content = ET.SubElement(contents, "Content", Name=self.asset_name, Type="particle_model")

        render_data = self.file_data.get("render")
        if render_data:
            content_object = ET.SubElement(content, "ContentObject", Name="", Type="particle_model")
            for data in render_data:
                self._write_network_files(content_object, data)

            output = ET.SubElement(content_object, "OutputTagCollection")
            if self.context.scene.nwo.particle_uses_custom_points:
                ET.SubElement(output, "OutputTag", Type="particle_emitter_custom_points").text = self.tag_path

    def _write_prefab_contents(self, metadata, sidecar_paths):
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

    def _write_skeleton_content(self, content):
        skeleton_data = self.file_data.get("skeleton")
        if skeleton_data:
            content_object = ET.SubElement(content, "ContentObject", Name="", Type="skeleton")
            self._write_network_files(content_object, skeleton_data[0])
            ET.SubElement(content_object, "OutputTagCollection")
        

    def _write_animation_content(self, content):
        animation_data = self.file_data.get("animation")
        if animation_data:
            content_object = ET.SubElement(content, "ContentObject", Name="", Type="model_animation_graph")
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

                network = ET.SubElement(content_object, "ContentNetwork", network_attribs)

                ET.SubElement(network, "InputFile").text = data.blend_path
                ET.SubElement(network, "IntermediateFile").text = data.gr2_path

            for action in bpy.data.actions:
                if not action.use_frame_range:
                    continue

                nwo = action.nwo
                renames = nwo.animation_renames
                for rename in renames:
                    network = ET.SubElement(
                        content_object,
                        "ContentNetwork",
                        Name=rename.name,
                        Type="Rename",
                        NetworkReference=nwo.name_override,
                    )
                    
            for item in self.context.scene.nwo.animation_copies:
                network = ET.SubElement(
                    content_object,
                    "ContentNetwork",
                    Name=item.name,
                    Type="Copy",
                    NetworkReference=item.source_name,
                )

            for item in self.context.scene.nwo.animation_composites:
                network = ET.SubElement(
                    content_object,
                    "ContentNetwork",
                    Name=item.name,
                    Type="CompositeOverlay" if item.overlay else "Composite",
                    NetworkReference=write_composite_xml(item),
                )
                
            output = ET.SubElement(content_object, "OutputTagCollection")
            ET.SubElement(output, "OutputTag", Type="frame_event_list").text = self.tag_path
            if self.corinth:
                ET.SubElement(output, "OutputTag", Type="pca_animation").text = self.tag_path
                
            ET.SubElement(output, "OutputTag", Type="model_animation_graph").text = self.tag_path

    def _region_active_state(self, region_name):
        region = self.context.scene.nwo.regions_table[region_name]
        return 'true' if region.active else 'false'
    
def write_composite_xml(composite) -> str:
    composite_xml = CompositeXML(composite)
    return composite_xml.build_xml()