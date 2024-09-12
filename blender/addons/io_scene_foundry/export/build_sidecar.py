from datetime import datetime
import os
from pathlib import Path
import bpy
import getpass
import xml.etree.cElementTree as ET
import xml.dom.minidom

from ..tools.animation.composites import CompositeXML

from ..utils import (
    get_data_path,
    is_corinth,
    relative_path,
)

class Sidecar:
    def __init__(self, asset_path, asset_name, asset_type, context):
        self.reach_world_animations = set()
        self.pose_overlays = set()
        self.tag_path = relative_path(Path(asset_path, asset_name))
        self.asset_path = asset_path
        self.asset_name = asset_name
        self.asset_type = asset_type
        if bpy.data.filepath and Path(bpy.data.filepath).is_relative_to(get_data_path()):
            self.relative_blend = str(Path(bpy.data.filepath).relative_to(get_data_path()))
        else:
            self.relative_blend = ""
        self.external_blend = self.relative_blend == bpy.data.filepath
        self.context = context
        self.message = f"{str.title(asset_type)} Sidecar Export Complete"

    def build(self, context, sidecar_path, sidecar_path_full, export_scene, sidecar_paths, sidecar_paths_design, scene_nwo, for_model_lighting=False):
        m_encoding = "utf-8"
        m_standalone = "yes"
        metadata = ET.Element("Metadata")
        # set a boolean to check if game is h4+ or not
        not_bungo_game = is_corinth()
        self.write_header(metadata)
        if self.asset_type == "model":
            self.get_object_output_types(
                metadata,
                "model",
                self.get_model_tags(
                    for_model_lighting,
                    scene_nwo.output_biped,
                    scene_nwo.output_crate,
                    scene_nwo.output_creature,
                    scene_nwo.output_device_control,
                    scene_nwo.output_device_dispenser,
                    scene_nwo.output_device_machine,
                    scene_nwo.output_device_terminal,
                    scene_nwo.output_effect_scenery,
                    scene_nwo.output_equipment,
                    scene_nwo.output_giant,
                    scene_nwo.output_scenery,
                    scene_nwo.output_vehicle,
                    scene_nwo.output_weapon,
                ),
            )
        elif self.asset_type.endswith("scenario"):
            self.get_object_output_types(
                metadata,
                "scenario",
            )
        elif self.asset_type == "sky":
            self.get_object_output_types(
                metadata,
                "sky" if not not_bungo_game else "model",
            )
        elif self.asset_type == "decorator_set":
            self.get_object_output_types(
                metadata,
                "decorator_set",
                "decorator_set",
            )
        elif self.asset_type == "particle_model":
            self.get_object_output_types(
                metadata,
                "particle_model",
                "particle_model",
            )
        elif self.asset_type == "prefab":
            self.get_object_output_types(
                metadata,
                "prefab",
                "prefab",
            )
        elif self.asset_type == "animation":
            self.get_object_output_types(
                metadata,
                "model",
            )

        self.write_folders(metadata, not_bungo_game)
        self.write_face_collections(
            metadata,
            not_bungo_game,
            export_scene.regions,
            export_scene.global_materials_dict,
            context,
        )

        if self.asset_type == "model":
            self.write_model_contents(metadata, sidecar_paths, bool(export_scene.model_armature))

        elif self.asset_type == "scenario":
            self.write_scenario_contents(
                export_scene,
                metadata,
                sidecar_paths,
                sidecar_paths_design,
            )

        elif self.asset_type == "model scenario":
            self.write_model_scenario_contents(metadata, sidecar_paths)

        elif self.asset_type == "sky":
            self.write_sky_contents(metadata, sidecar_paths)

        elif self.asset_type == "decorator_set":
            self.write_decorator_contents(metadata, sidecar_paths, export_scene.lods)

        elif self.asset_type == "particle_model":
            self.write_particle_contents(metadata, sidecar_paths)

        elif self.asset_type == "prefab":
            self.write_prefab_contents(metadata, sidecar_paths)

        elif self.asset_type == "animation":
            self.write_fp_animation_contents(
                metadata, sidecar_paths
            )

        dom = xml.dom.minidom.parseString(ET.tostring(metadata))
        xml_string = dom.toprettyxml(indent="  ")
        part1, part2 = xml_string.split("?>")

        if self.asset_type == "model scenario":
            sidecar_path_full = sidecar_path_full.replace(
                f"{self.asset_name}.sidecar.xml",
                f"{self.asset_name}_lighting.sidecar.xml",
            )
        else:
            # update sidecar path in halo launcher
            context.scene.nwo.sidecar_path = sidecar_path

        if Path(sidecar_path_full).exists():
            if not os.access(sidecar_path_full, os.W_OK):
                raise RuntimeError(f"Sidecar is read only, cannot complete export: {sidecar_path_full}\n")
        
        with open(sidecar_path_full, "w") as xfile:
            xfile.write(
                part1
                + 'encoding="{}" standalone="{}"?>'.format(m_encoding, m_standalone)
                + part2
            )

    def write_header(self, metadata):
        header = ET.SubElement(metadata, "Header")
        ET.SubElement(header, "MainRev").text = "0"
        ET.SubElement(header, "PointRev").text = "6"
        ET.SubElement(header, "Description").text = "Forged in Foundry"
        ET.SubElement(header, "Created").text = str(
            datetime.today().strftime("%Y-%m-%d %H:%M:%S")
        )
        ET.SubElement(header, "By").text = getpass.getuser()
        ET.SubElement(header, "SourceBlend").text = self.relative_blend
        ET.SubElement(header, "DirectoryType").text = "TAE.Shared.NWOAssetDirectory"
        ET.SubElement(header, "Schema").text = "1"

    def get_model_tags(
        self,
        for_model_lighting,
        output_biped=False,
        output_crate=False,
        output_creature=False,
        output_device_control=False,
        output_device_dispenser=False,
        output_device_machine=False,
        output_device_terminal=False,
        output_effect_scenery=False,
        output_equipment=False,
        output_giant=False,
        output_scenery=False,
        output_vehicle=False,
        output_weapon=False,
    ):
        tags = ["model"]
        if not for_model_lighting:
            if output_biped:
                tags.append("biped")
            if output_crate:
                tags.append("crate")
            if output_creature:
                tags.append("creature")
            if output_device_control:
                tags.append("device_control")
            if output_device_dispenser:
                tags.append("device_dispenser")
            if output_device_machine:
                tags.append("device_machine")
            if output_device_terminal:
                tags.append("device_terminal")
            if output_effect_scenery:
                tags.append("effect_scenery")
            if output_equipment:
                tags.append("equipment")
            if output_giant:
                tags.append("giant")
            if output_scenery:
                tags.append("scenery")
            if output_vehicle:
                tags.append("vehicle")
            if output_weapon:
                tags.append("weapon")
        if len(tags) == 1:
            # Must have high level tag, but we can delete this post export
            tags.append("scenery")
            self.no_top_level_tag = True


        return tags

    def get_object_output_types(
        self,
        metadata,
        type,
        output_tags=[],
    ):
        if self.asset_type == "sky":
            asset = ET.SubElement(
                metadata, "Asset", Name=self.asset_name, Type=type, Sky="true"
            )
        else:
            asset = ET.SubElement(metadata, "Asset", Name=self.asset_name, Type=type)
        tagcollection = ET.SubElement(asset, "OutputTagCollection")

        if type == "model" and self.asset_type == "model":
            for (
                tag
            ) in (
                output_tags
            ):  # for each output tag that that user as opted to export, add this to the sidecar
                ET.SubElement(tagcollection, "OutputTag", Type=tag).text = self.tag_path
        # models are the only sidecar type with optional high level tags exports, all others are fixed
        elif type == "scenario":
            ET.SubElement(
                tagcollection, "OutputTag", Type="scenario_lightmap"
            ).text = f"{self.tag_path}_faux_lightmap"
            ET.SubElement(
                tagcollection, "OutputTag", Type="structure_seams"
            ).text = self.tag_path
            ET.SubElement(
                tagcollection, "OutputTag", Type="scenario"
            ).text = self.tag_path

        elif type == "decorator_set":
            ET.SubElement(
                tagcollection, "OutputTag", Type="decorator_set"
            ).text = self.tag_path

        elif type == "particle_model":
            ET.SubElement(tagcollection, "OutputTag", Type="particle_model").text = self.tag_path

        elif type == "prefab":
            ET.SubElement(
                tagcollection, "OutputTag", Type="prefab"
            ).text = self.tag_path

        else:  # sky & fp animation
            ET.SubElement(tagcollection, "OutputTag", Type="model").text = self.tag_path
            ET.SubElement(
                tagcollection, "OutputTag", Type="scenery"
            ).text = self.tag_path

        # TODO reimplement shared asset stuff before this can be uncommented
        # shared = ET.SubElement(asset, "SharedAssetCollection")
        # # create a shared asset entry for each that exists
        # shared_assets = context.scene.nwo.shared_assets
        # for asset in shared_assets:
        #     ET.SubElement(shared, "SharedAsset", Type=f'TAE.Shared.{asset.shared_asset_type}').text = asset.shared_asset_path

    def write_folders(self, metadata, not_bungie_game):
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
        ET.SubElement(
            folders, "FacePoses"
        ).text = "\\animations\\rigs\\poses\\face_poses"
        ET.SubElement(folders, "CinematicOutsource").text = "\\outsource"

        if not_bungie_game:
            ET.SubElement(folders, "Retarget").text = "\\working\\retarget"
            ET.SubElement(
                folders, "RetargetSourceAnimations"
            ).text = "\\working\\retarget\\binge"
            ET.SubElement(
                folders, "RetargetTargetAnimations"
            ).text = "\\working\\retarget\\purge"
            ET.SubElement(folders, "Export").text = "\\export"
            ET.SubElement(folders, "CinematicSceneSegments").text = "\\segments"
            ET.SubElement(
                folders, "SourceAnimationLibrary"
            ).text = "\\animations\\library"

    def write_face_collections(
        self,
        metadata,
        not_bungie_game,
        regions,
        global_materials_dict,
        context,
    ):  # FaceCollections is where regions and global materials are defined in the sidecar.
        faceCollections = ET.SubElement(metadata, "FaceCollections")

        # if self.asset_type == "scenario" and not_bungie_game:
        #     bsp_list = ["default", ""]
        #     f1 = ET.SubElement(
        #         faceCollections,
        #         "FaceCollection",
        #         Name="connected_geometry_bsp_table",
        #         StringTable="connected_geometry_bsp_table",
        #         Description="BSPs",
        #     )

            # FaceCollectionsEntries = ET.SubElement(f1, "FaceCollectionEntries")
            # using_default_bsp = 'default' in regions
            # if 

            # ET.SubElement(
            #     FaceCollectionsEntries,
            #     "FaceCollectionEntry",
            #     Index="0",
            #     Name="default",
            #     Active=str(using_default_bsp).lower(),
            # )
            
            # FaceCollectionsEntries = ET.SubElement(f1, "FaceCollectionEntries")
            # for idx, bsp in enumerate(regions):
            #     ET.SubElement(
            #         FaceCollectionsEntries,
            #         "FaceCollectionEntry",
            #         Index=str(idx),
            #         Name=bsp,
            #         Active=self.region_active_state(context, bsp),
            #     )

            # count = 1
            # for ob in bpy.context.view_layer.objects:
            #     bsp = ob.nwo.region_name
            #     if bsp not in bsp_list:
            #         ET.SubElement(
            #             FaceCollectionsEntries,
            #             "FaceCollectionEntry",
            #             Index=str(count),
            #             Name=bsp,
            #             Active="true",
            #         )
            #         bsp_list.append(bsp)
            #         count += 1

        if self.asset_type in ("model", "sky"):
            f1 = ET.SubElement(
                faceCollections,
                "FaceCollection",
                Name="regions",
                StringTable="connected_geometry_regions_table",
                Description="Model regions",
            )

            FaceCollectionsEntries = ET.SubElement(f1, "FaceCollectionEntries")
            for idx, region in enumerate(regions):
                ET.SubElement(
                    FaceCollectionsEntries,
                    "FaceCollectionEntry",
                    Index=str(idx),
                    Name=region,
                    Active=self.region_active_state(context, region),
                )

        if self.asset_type in ("model", "scenario", "prefab", "sky"):
            f2 = ET.SubElement(
                faceCollections,
                "FaceCollection",
                Name="global materials override",
                StringTable="connected_geometry_global_material_table",
                Description="Global material overrides",
            )

            FaceCollectionsEntries2 = ET.SubElement(f2, "FaceCollectionEntries")
            for global_material in global_materials_dict.keys():
                ET.SubElement(
                    FaceCollectionsEntries2,
                    "FaceCollectionEntry",
                    Index=str(global_materials_dict.get(global_material)),
                    Name=global_material,
                    Active="true",
                )

    def write_network_files(self, object, path):
        network = ET.SubElement(object, "ContentNetwork", Name=path[3], Type="")
        ET.SubElement(network, "InputFile").text = self.relative_blend if not self.external_blend else path[0]
        # ET.SubElement(network, "ComponentFile").text = path[1]
        ET.SubElement(network, "IntermediateFile").text = path[2]

    def write_model_contents(self, metadata, sidecar_paths, has_skeleton):
        contents = ET.SubElement(metadata, "Contents")
        content = ET.SubElement(contents, "Content", Name=self.asset_name, Type="model")
        ##### RENDER #####
        object = ET.SubElement(content, "ContentObject", Name="", Type="render_model")
        render_paths = sidecar_paths.get("render")
        for path in render_paths:
            self.write_network_files(object, path)

        output = ET.SubElement(object, "OutputTagCollection")
        ET.SubElement(output, "OutputTag", Type="render_model").text = self.tag_path

        ##### PHYSICS #####
        if "physics" in sidecar_paths.keys():
            object = ET.SubElement(
                content, "ContentObject", Name="", Type="physics_model"
            )
            physics_paths = sidecar_paths.get("physics")
            for path in physics_paths:
                self.write_network_files(object, path)

            output = ET.SubElement(object, "OutputTagCollection")
            ET.SubElement(
                output, "OutputTag", Type="physics_model"
            ).text = self.tag_path

        ##### COLLISION #####
        if "collision" in sidecar_paths.keys():
            object = ET.SubElement(
                content, "ContentObject", Name="", Type="collision_model"
            )

            collision_paths = sidecar_paths.get("collision")
            for path in collision_paths:
                self.write_network_files(object, path)

            output = ET.SubElement(object, "OutputTagCollection")
            ET.SubElement(
                output, "OutputTag", Type="collision_model"
            ).text = self.tag_path

        ##### SKELETON #####
        if has_skeleton:
            self.write_skeleton_content(content, sidecar_paths)

        ##### MARKERS #####
        if "markers" in sidecar_paths.keys():
            object = ET.SubElement(content, "ContentObject", Name="", Type="markers")
            network = ET.SubElement(object, "ContentNetwork", Name="default", Type="")

            path = sidecar_paths.get("markers")[0]

            ET.SubElement(network, "InputFile").text = self.relative_blend if not self.external_blend else path[0]
            # ET.SubElement(network, "ComponentFile").text = path[1]
            ET.SubElement(network, "IntermediateFile").text = path[2]

            output = ET.SubElement(object, "OutputTagCollection")

        ##### ANIMATIONS #####
        if has_skeleton:
            self.write_animation_content(content, sidecar_paths)

    def write_network_files_bsp(self, object, path, asset_name, bsp):
        perm = path[3]
        if perm == "default":
            network = ET.SubElement(
                object, "ContentNetwork", Name=f"{asset_name}_{bsp}", Type=""
            )
        else:
            network = ET.SubElement(
                object,
                "ContentNetwork",
                Name=f"{asset_name}_{bsp}_{path[3]}",
                Type="",
            )

        ET.SubElement(network, "InputFile").text = self.relative_blend if not self.external_blend else path[0]
        # ET.SubElement(network, "ComponentFile").text = path[1]
        ET.SubElement(network, "IntermediateFile").text = path[2]

    def write_model_scenario_contents(self, metadata, sidecar_paths):
        contents = ET.SubElement(metadata, "Contents")
        content = ET.SubElement(contents, "Content", Name=f"{self.asset_name}", Type="bsp")
        object = ET.SubElement(
            content,
            "ContentObject",
            Name="",
            Type="scenario_structure_bsp",
        )
        lighting_path = sidecar_paths.get("lighting")[0]
        network = ET.SubElement(object, "ContentNetwork", Name=f"{self.asset_name}", Type="")

        ET.SubElement(network, "InputFile").text = self.relative_blend if not self.external_blend else self.asset_path
        # ET.SubElement(network, "ComponentFile").text = lighting_path[1]
        ET.SubElement(network, "IntermediateFile").text = lighting_path[2]

        output = ET.SubElement(object, "OutputTagCollection")
        ET.SubElement(
            output, "OutputTag", Type="scenario_structure_bsp"
        ).text = f"{self.tag_path}"
        ET.SubElement(
            output, "OutputTag", Type="scenario_structure_lighting_info"
        ).text = f"{self.tag_path}"

    def write_scenario_contents(
        self, export_scene, metadata, sidecar_paths, design_paths
    ):
        contents = ET.SubElement(metadata, "Contents")
        ##### STRUCTURE #####
        scene_bsps = [b for b in export_scene.structure_bsps if b != "shared"]
        shared = len(scene_bsps) != len(export_scene.regions)
        for bsp in scene_bsps:
            content = ET.SubElement(
                contents, "Content", Name=f"{self.asset_name}_{bsp}", Type="bsp"
            )
            object = ET.SubElement(
                content,
                "ContentObject",
                Name="",
                Type="scenario_structure_bsp",
            )
            bsp_paths = sidecar_paths.get(bsp)
            for path in bsp_paths:
                self.write_network_files_bsp(object, path, self.asset_name, bsp)

            if shared:
                shared_paths = sidecar_paths.get('shared')
                for path in shared_paths:
                    self.write_network_files_bsp(object, path, self.asset_name, "shared")

            output = ET.SubElement(object, "OutputTagCollection")
            ET.SubElement(
                output, "OutputTag", Type="scenario_structure_bsp"
            ).text = f"{self.tag_path}_{bsp}"
            ET.SubElement(
                output, "OutputTag", Type="scenario_structure_lighting_info"
            ).text = f"{self.tag_path}_{bsp}"

        ##### STRUCTURE DESIGN #####
        scene_design = export_scene.design_bsps

        for bsp in scene_design:
            bsp_paths = design_paths.get(bsp)
            content = ET.SubElement(
                contents,
                "Content",
                Name=f"{self.asset_name}_{bsp}_structure_design",
                Type="design",
            )
            object = ET.SubElement(
                content, "ContentObject", Name="", Type="structure_design"
            )

            if not bsp_paths: continue
            for path in bsp_paths:
                self.write_network_files_bsp(object, path, self.asset_name, bsp)

            output = ET.SubElement(object, "OutputTagCollection")
            ET.SubElement(
                output, "OutputTag", Type="structure_design"
            ).text = f"{self.tag_path}_{bsp}_structure_design"

    def write_sky_contents(self, metadata, sidecar_paths):
        contents = ET.SubElement(metadata, "Contents")
        content = ET.SubElement(contents, "Content", Name=self.asset_name, Type="model")
        object = ET.SubElement(content, "ContentObject", Name="", Type="render_model")

        path = sidecar_paths.get("sky")[0]

        network = ET.SubElement(object, "ContentNetwork", Name="default", Type="")
        ET.SubElement(network, "InputFile").text = self.relative_blend if not self.external_blend else path[0]
        # ET.SubElement(network, "ComponentFile").text = path[1]
        ET.SubElement(network, "IntermediateFile").text = path[2]
        
        if "markers" in sidecar_paths.keys():
            object = ET.SubElement(content, "ContentObject", Name="", Type="markers")
            network = ET.SubElement(object, "ContentNetwork", Name="default", Type="")

            path = sidecar_paths.get("markers")[0]

            ET.SubElement(network, "InputFile").text = self.relative_blend if not self.external_blend else path[0]
            # ET.SubElement(network, "ComponentFile").text = path[1]
            ET.SubElement(network, "IntermediateFile").text = path[2]

            output = ET.SubElement(object, "OutputTagCollection")

        output = ET.SubElement(object, "OutputTagCollection")
        ET.SubElement(output, "OutputTag", Type="render_model").text = self.tag_path

    def write_decorator_contents(self, metadata, sidecar_paths, lods):
        contents = ET.SubElement(metadata, "Contents")
        content = ET.SubElement(
            contents, "Content", Name=self.asset_name, Type="decorator_set"
        )

        decorator_path = sidecar_paths.get("decorator")[0]
        for lod in lods:
            lod_str = str(lod - 1)
            object = ET.SubElement(
                content,
                "ContentObject",
                Name=lod_str,
                Type="render_model",
                LOD=lod_str,
            )
            network = ET.SubElement(object, "ContentNetwork", Name="default", Type="")

            ET.SubElement(network, "InputFile").text = self.relative_blend if not self.external_blend else self.asset_path
            # ET.SubElement(network, "ComponentFile").text = path[1]
            ET.SubElement(network, "IntermediateFile").text = decorator_path[2]

            output = ET.SubElement(object, "OutputTagCollection")
            ET.SubElement(
                output, "OutputTag", Type="render_model"
            ).text = f"{self.tag_path}_lod{lod}"

        output = ET.SubElement(object, "OutputTagCollection")

    def write_particle_contents(self, metadata, sidecar_paths):
        contents = ET.SubElement(metadata, "Contents")
        content = ET.SubElement(
            contents, "Content", Name=self.asset_name, Type="particle_model"
        )
        object = ET.SubElement(content, "ContentObject", Name="", Type="particle_model")

        path = sidecar_paths.get("particle_model")[0]

        network = ET.SubElement(object, "ContentNetwork", Name=self.asset_name, Type="")
        ET.SubElement(network, "InputFile").text = self.relative_blend if not self.external_blend else path[0]
        # ET.SubElement(network, "ComponentFile").text = path[1]
        ET.SubElement(network, "IntermediateFile").text = path[2]

        output = ET.SubElement(object, "OutputTagCollection")
        if self.context.scene.nwo.particle_uses_custom_points:
            ET.SubElement(output, "OutputTag", Type="particle_emitter_custom_points").text = self.tag_path

    def write_prefab_contents(self, metadata, sidecar_paths):
        contents = ET.SubElement(metadata, "Contents")
        content = ET.SubElement(contents, "Content", Name=self.asset_name, Type="prefab")
        object = ET.SubElement(
            content, "ContentObject", Name="", Type="scenario_structure_bsp"
        )

        path = sidecar_paths.get("prefab")[0]

        network = ET.SubElement(object, "ContentNetwork", Name=self.asset_name, Type="")
        ET.SubElement(network, "InputFile").text = self.relative_blend if not self.external_blend else path[0]
        # ET.SubElement(network, "ComponentFile").text = path[1]
        ET.SubElement(network, "IntermediateFile").text = path[2]

        output = ET.SubElement(object, "OutputTagCollection")
        ET.SubElement(
            output, "OutputTag", Type="scenario_structure_bsp"
        ).text = self.tag_path
        ET.SubElement(
            output, "OutputTag", Type="scenario_structure_lighting_info"
        ).text = self.tag_path

    def write_fp_animation_contents(
        self, metadata, sidecar_paths
    ):
        # NULL RENDER
        contents = ET.SubElement(metadata, "Contents")
        content = ET.SubElement(contents, "Content", Name=self.asset_name, Type="model")
        object = ET.SubElement(content, "ContentObject", Name="", Type="render_model")
        path = sidecar_paths.get("render")[0]
        network = ET.SubElement(object, "ContentNetwork", Name="default", Type="")
        ET.SubElement(network, "InputFile").text = self.relative_blend if not self.external_blend else path[0]
        ET.SubElement(network, "IntermediateFile").text = path[2]

        output = ET.SubElement(object, "OutputTagCollection")
        ET.SubElement(output, "OutputTag", Type="render_model").text = self.tag_path

        ##### SKELETON #####
        self.write_skeleton_content(content, sidecar_paths)

        ##### ANIMATIONS #####
        self.write_animation_content(content, sidecar_paths)

    def write_skeleton_content(self, content, sidecar_paths):
        object = ET.SubElement(content, "ContentObject", Name="", Type="skeleton")
        network = ET.SubElement(object, "ContentNetwork", Name="default", Type="")

        path = sidecar_paths.get("skeleton")[0]

        ET.SubElement(network, "InputFile").text = self.relative_blend if not self.external_blend else path[0]
        # ET.SubElement(network, "ComponentFile").text = path[1]
        ET.SubElement(network, "IntermediateFile").text = path[2]

        output = ET.SubElement(object, "OutputTagCollection")

    def write_animation_content(self, content, sidecar_paths):
        if "animation" in sidecar_paths.keys():
            object = ET.SubElement(
                content, "ContentObject", Name="", Type="model_animation_graph"
            )
            animation_paths = sidecar_paths.get("animation")
            for path in animation_paths:
                compression = path[8] if path[8] != "Default" else None
                network_attribs = {"Name": path[3], "Type": "Base"}
                a_type = path[4]
                movement = path[5]
                space = path[6]
                pose_overlay = path[7]
                if a_type == 'overlay':
                    network_attribs['Type'] = "Overlay"
                    network_attribs['ModelAnimationOverlayBlending'] = "Additive"
                    if pose_overlay:
                        network_attribs['ModelAnimationOverlayType'] = "Pose"
                        self.pose_overlays.add(path[3].replace(' ', ':'))
                    else:
                        network_attribs['ModelAnimationOverlayType'] = "Keyframe"
                elif a_type == 'world' and is_corinth():
                    network_attribs['Type'] = "World"
                    network_attribs['ModelAnimationMovementData'] = "XYZAbsolute"
                elif a_type == 'replacement':
                    network_attribs['Type'] = "Overlay"
                    network_attribs['ModelAnimationOverlayType'] = "Keyframe"
                    if space == 'object':
                        network_attribs['ModelAnimationOverlayBlending'] = "ReplacementObjectSpace"
                    else:
                        network_attribs['ModelAnimationOverlayBlending'] = "ReplacementLocalSpace"
                else:
                    if a_type == 'world':
                        self.reach_world_animations.add(path[3].replace(' ', ':'))
                    elif movement == 'none':
                        network_attribs['ModelAnimationMovementData'] = "None"
                    elif movement == 'xy':
                        network_attribs['ModelAnimationMovementData'] = "XY"
                    elif movement == 'xyyaw':
                        network_attribs['ModelAnimationMovementData'] = "XYYaw"
                    elif movement == 'xyzyaw':
                        network_attribs['ModelAnimationMovementData'] = "XYZYaw"
                    else:
                        network_attribs['ModelAnimationMovementData'] = "XYZFullRotation"
                    
                if compression is not None:
                    network_attribs['Compression'] = compression

                network = ET.SubElement(object, "ContentNetwork", network_attribs)

                ET.SubElement(network, "InputFile").text = self.relative_blend if not self.external_blend else path[0]
                # ET.SubElement(network, "ComponentFile").text = path[1]
                ET.SubElement(network, "IntermediateFile").text = path[2]

            for action in bpy.data.actions:
                if not action.use_frame_range:
                    continue

                nwo = action.nwo
                renames = nwo.animation_renames
                for rename in renames:
                    network = ET.SubElement(
                        object,
                        "ContentNetwork",
                        Name=rename.name,
                        Type="Rename",
                        NetworkReference=nwo.name_override,
                    )
                    
            for item in self.context.scene.nwo.animation_copies:
                network = ET.SubElement(
                    object,
                    "ContentNetwork",
                    Name=item.name,
                    Type="Copy",
                    NetworkReference=item.source_name,
                )

            for item in self.context.scene.nwo.animation_composites:
                network = ET.SubElement(
                    object,
                    "ContentNetwork",
                    Name=item.name,
                    Type="CompositeOverlay" if item.overlay else "Composite",
                    NetworkReference=write_composite_xml(item),
                )
                
            output = ET.SubElement(object, "OutputTagCollection")
            ET.SubElement(
                output, "OutputTag", Type="frame_event_list"
            ).text = self.tag_path
            if is_corinth():
                ET.SubElement(
                    output, "OutputTag", Type="pca_animation"
                ).text = self.tag_path
            ET.SubElement(
                output, "OutputTag", Type="model_animation_graph"
            ).text = self.tag_path

    def region_active_state(self, context, region_name):
        region = context.scene.nwo.regions_table[region_name]
        return 'true' if region.active else 'false'
    
def write_composite_xml(composite) -> str:
    composite_xml = CompositeXML(composite)
    return composite_xml.build_xml()