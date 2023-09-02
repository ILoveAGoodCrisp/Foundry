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

from datetime import datetime
import bpy
import getpass
import xml.etree.cElementTree as ET
import xml.dom.minidom
import os
import shutil

from ..utils.nwo_utils import (
    data_relative,
    get_data_path,
    is_corinth,
)


class Sidecar:
    def __init__(
        self,
        context,
        sidecar_path,
        sidecar_path_full,
        asset_path,
        asset_name,
        nwo_scene,
        sidecar_paths,
        sidecar_paths_design,
        sidecar_type,
        output_biped,
        output_crate,
        output_creature,
        output_device_control,
        output_device_dispenser,
        output_device_machine,
        output_device_terminal,
        output_effect_scenery,
        output_equipment,
        output_giant,
        output_scenery,
        output_vehicle,
        output_weapon,
    ):
        self.tag_path = data_relative(os.path.join(asset_path, asset_name))
        self.relative_blend = bpy.data.filepath.replace(get_data_path(), "")
        self.external_blend = False
        if self.relative_blend == bpy.data.filepath:
            self.external_blend = True

        self.build_sidecar(
            nwo_scene,
            sidecar_path,
            sidecar_path_full,
            asset_path,
            asset_name,
            sidecar_paths,
            sidecar_paths_design,
            sidecar_type,
            context,
            output_biped,
            output_crate,
            output_creature,
            output_device_control,
            output_device_dispenser,
            output_device_machine,
            output_device_terminal,
            output_effect_scenery,
            output_equipment,
            output_giant,
            output_scenery,
            output_vehicle,
            output_weapon,
        )

        del self.tag_path
        del self.relative_blend

        self.message = f"{str.title(sidecar_type)} Sidecar Export Complete"

    def build_sidecar(
        self,
        nwo_scene,
        sidecar_path,
        sidecar_path_full,
        asset_path,
        asset_name,
        sidecar_paths,
        sidecar_paths_design,
        sidecar_type,
        context,
        output_biped,
        output_crate,
        output_creature,
        output_device_control,
        output_device_dispenser,
        output_device_machine,
        output_device_terminal,
        output_effect_scenery,
        output_equipment,
        output_giant,
        output_scenery,
        output_vehicle,
        output_weapon,
    ):
        m_encoding = "utf-8"
        m_standalone = "yes"
        metadata = ET.Element("Metadata")
        # set a boolean to check if game is h4+ or not
        not_bungo_game = is_corinth()
        self.write_header(metadata)
        if sidecar_type == "MODEL":
            self.get_object_output_types(
                metadata,
                "model",
                asset_name,
                sidecar_type,
                self.get_model_tags(
                    output_biped,
                    output_crate,
                    output_creature,
                    output_device_control,
                    output_device_dispenser,
                    output_device_machine,
                    output_device_terminal,
                    output_effect_scenery,
                    output_equipment,
                    output_giant,
                    output_scenery,
                    output_vehicle,
                    output_weapon,
                ),
            )
        elif sidecar_type.endswith("SCENARIO"):
            self.get_object_output_types(
                metadata,
                "scenario",
                asset_name,
                sidecar_type,
            )
        elif sidecar_type == "SKY":
            self.get_object_output_types(
                metadata,
                "sky" if not not_bungo_game else "model",
                asset_name,
                sidecar_type,
            )
        elif sidecar_type == "DECORATOR SET":
            self.get_object_output_types(
                metadata,
                "decorator_set",
                asset_name,
                sidecar_type,
                "decorator_set",
            )
        elif sidecar_type == "PARTICLE MODEL":
            self.get_object_output_types(
                metadata,
                "particle_model",
                asset_name,
                sidecar_type,
                "particle_model",
            )
        elif sidecar_type == "PREFAB":
            self.get_object_output_types(
                metadata,
                "prefab",
                asset_name,
                sidecar_type,
                "prefab",
            )
        elif sidecar_type == "FP ANIMATION":
            self.get_object_output_types(
                metadata,
                "model",
                asset_name,
                sidecar_type,
            )

        self.write_folders(metadata, not_bungo_game)
        self.write_face_collections(
            metadata,
            sidecar_type,
            not_bungo_game,
            nwo_scene.regions_table,
            nwo_scene.global_materials_dict,
        )

        if sidecar_type == "MODEL":
            self.write_model_contents(metadata, sidecar_paths, asset_name, asset_path, bool(nwo_scene.model_armature))

        elif sidecar_type == "SCENARIO":
            self.write_scenario_contents(
                nwo_scene,
                metadata,
                sidecar_paths,
                sidecar_paths_design,
                asset_name,
            )

        elif sidecar_type == "MODEL SCENARIO":
            self.write_model_scenario_contents(metadata, sidecar_paths, asset_name)

        elif sidecar_type == "SKY":
            self.write_sky_contents(metadata, sidecar_paths, asset_name)

        elif sidecar_type == "DECORATOR SET":
            self.write_decorator_contents(metadata, sidecar_paths, asset_name, nwo_scene.lods)

        elif sidecar_type == "PARTICLE MODEL":
            self.write_particle_contents(metadata, sidecar_paths, asset_name)

        elif sidecar_type == "PREFAB":
            self.write_prefab_contents(metadata, sidecar_paths, asset_name)

        elif sidecar_type == "FP ANIMATION":
            self.add_null_render(asset_path)
            self.write_fp_animation_contents(
                metadata, sidecar_paths, asset_path, asset_name
            )

        dom = xml.dom.minidom.parseString(ET.tostring(metadata))
        xml_string = dom.toprettyxml(indent="  ")
        part1, part2 = xml_string.split("?>")

        if sidecar_type == "MODEL SCENARIO":
            sidecar_path_full = sidecar_path_full.replace(
                f"{asset_name}.sidecar.xml",
                f"{asset_name}_lighting.sidecar.xml",
            )
        else:
            # update sidecar path in halo launcher
            context.scene.nwo_halo_launcher.sidecar_path = sidecar_path

        with open(sidecar_path_full, "w") as xfile:
            xfile.write(
                part1
                + 'encoding="{}" standalone="{}"?>'.format(m_encoding, m_standalone)
                + part2
            )
            xfile.close()

    def add_null_render(self, asset_path):
        null_gr2_path = os.path.join(asset_path, "export", "models", "null_render.gr2")
        if not os.path.exists(null_gr2_path):
            # copy the null gr2 from io_scene_nwo to act as the render model
            try:
                script_folder_path = os.path.dirname(os.path.dirname(__file__))
                null_gr2 = os.path.join(
                    script_folder_path,
                    "export",
                    "resources",
                    "null_render.gr2",
                )
                shutil.copy(null_gr2, null_gr2_path)
            except:
                print("Unable to copy null gr2 from io_scene_foundry to asset folder")

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
        elif len(tags) == 1:
            # Must have high level tag, but we can delete this post export
            tags.append("scenery")
            self.no_top_level_tag = True


        return tags

    def get_object_output_types(
        self,
        metadata,
        type,
        asset_name,
        sidecar_type,
        output_tags=[],
    ):
        if sidecar_type == "SKY":
            asset = ET.SubElement(
                metadata, "Asset", Name=asset_name, Type=type, Sky="true"
            )
        else:
            asset = ET.SubElement(metadata, "Asset", Name=asset_name, Type=type)
        tagcollection = ET.SubElement(asset, "OutputTagCollection")

        if type == "model" and sidecar_type == "MODEL":
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
            ET.SubElement(
                tagcollection, "OutputTag", Type="particle_model"
            ).text = self.tag_path

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
        sidecar_type,
        not_bungie_game,
        regions_table,
        global_materials_dict,
    ):  # FaceCollections is where regions and global materials are defined in the sidecar.
        faceCollections = ET.SubElement(metadata, "FaceCollections")

        if sidecar_type == "SCENARIO" and not_bungie_game:
            bsp_list = ["default", ""]
            f1 = ET.SubElement(
                faceCollections,
                "FaceCollection",
                Name="connected_geometry_bsp_table",
                StringTable="connected_geometry_bsp_table",
                Description="BSPs",
            )

            FaceCollectionsEntries = ET.SubElement(f1, "FaceCollectionEntries")
            using_default_bsp = False
            for ob in bpy.context.view_layer.objects:
                bsp = ob.nwo.bsp_name
                if bsp == "default":
                    using_default_bsp = True
                    break

            ET.SubElement(
                FaceCollectionsEntries,
                "FaceCollectionEntry",
                Index="0",
                Name="default",
                Active=str(using_default_bsp).lower(),
            )

            count = 1
            for ob in bpy.context.view_layer.objects:
                bsp = ob.nwo.bsp_name
                if bsp not in bsp_list:
                    ET.SubElement(
                        FaceCollectionsEntries,
                        "FaceCollectionEntry",
                        Index=str(count),
                        Name=bsp,
                        Active="true",
                    )
                    bsp_list.append(bsp)
                    count += 1

        if sidecar_type in ("MODEL", "SKY"):
            f1 = ET.SubElement(
                faceCollections,
                "FaceCollection",
                Name="regions",
                StringTable="connected_geometry_regions_table",
                Description="Model regions",
            )

            FaceCollectionsEntries = ET.SubElement(f1, "FaceCollectionEntries")
            for region in regions_table:
                ET.SubElement(
                    FaceCollectionsEntries,
                    "FaceCollectionEntry",
                    Index=str(regions_table.keys().index(region.name)),
                    Name=region.name,
                    Active="true" if region.active else "false",
                )

        if sidecar_type in ("MODEL", "SCENARIO", "PREFAB", "SKY"):
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

    def write_model_contents(self, metadata, sidecar_paths, asset_name, asset_path, has_skeleton):
        contents = ET.SubElement(metadata, "Contents")
        content = ET.SubElement(contents, "Content", Name=asset_name, Type="model")
        ##### RENDER #####
        object = ET.SubElement(content, "ContentObject", Name="", Type="render_model")
        render_paths = sidecar_paths.get("render")
        if render_paths is None:
            # NULL RENDER
            self.add_null_render(asset_path)
            network = ET.SubElement(object, "ContentNetwork", Name="default", Type="")
            ET.SubElement(network, "InputFile").text = self.relative_blend if not self.external_blend else path[0]
            ET.SubElement(network, "IntermediateFile").text = os.path.join(
                asset_path.replace(get_data_path(), ""),
                "export",
                "models",
                "null_render.gr2",
            )
        else:
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

    def write_model_scenario_contents(self, metadata, sidecar_paths, asset_name):
        contents = ET.SubElement(metadata, "Contents")
        content = ET.SubElement(contents, "Content", Name=f"{asset_name}", Type="bsp")
        object = ET.SubElement(
            content,
            "ContentObject",
            Name="",
            Type="scenario_structure_bsp",
        )
        lighting_path = sidecar_paths.get("lighting")[0]
        network = ET.SubElement(object, "ContentNetwork", Name=f"{asset_name}", Type="")

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
        self, nwo_scene, metadata, sidecar_paths, design_paths, asset_name
    ):
        contents = ET.SubElement(metadata, "Contents")
        ##### STRUCTURE #####
        scene_bsps = [b for b in nwo_scene.structure_bsps if b != "shared"]
        shared = len(scene_bsps) != len(nwo_scene.structure_bsps)

        for bsp in scene_bsps:
            content = ET.SubElement(
                contents, "Content", Name=f"{asset_name}_{bsp}", Type="bsp"
            )
            object = ET.SubElement(
                content,
                "ContentObject",
                Name="",
                Type="scenario_structure_bsp",
            )
            bsp_paths = sidecar_paths.get(bsp)
            for path in bsp_paths:
                self.write_network_files_bsp(object, path, asset_name, bsp)

            if shared:
                shared_paths = [i for i in sidecar_paths if i == "shared"]
                for path in shared_paths:
                    self.write_network_files_bsp(object, path, asset_name, "shared")

            output = ET.SubElement(object, "OutputTagCollection")
            ET.SubElement(
                output, "OutputTag", Type="scenario_structure_bsp"
            ).text = f"{self.tag_path}_{bsp}"
            ET.SubElement(
                output, "OutputTag", Type="scenario_structure_lighting_info"
            ).text = f"{self.tag_path}_{bsp}"

        ##### STRUCTURE DESIGN #####
        scene_design = nwo_scene.design_bsps

        for bsp in scene_design:
            content = ET.SubElement(
                contents,
                "Content",
                Name=f"{asset_name}_{bsp}_structure_design",
                Type="design",
            )
            object = ET.SubElement(
                content, "ContentObject", Name="", Type="structure_design"
            )

            bsp_paths = design_paths.get(bsp)
            for path in bsp_paths:
                self.write_network_files_bsp(object, path, asset_name, bsp)

            output = ET.SubElement(object, "OutputTagCollection")
            ET.SubElement(
                output, "OutputTag", Type="structure_design"
            ).text = f"{self.tag_path}_{bsp}_structure_design"

    def write_sky_contents(self, metadata, sidecar_paths, asset_name):
        contents = ET.SubElement(metadata, "Contents")
        content = ET.SubElement(contents, "Content", Name=asset_name, Type="model")
        object = ET.SubElement(content, "ContentObject", Name="", Type="render_model")

        path = sidecar_paths.get("sky")[0]

        network = ET.SubElement(object, "ContentNetwork", Name="default", Type="")
        ET.SubElement(network, "InputFile").text = self.relative_blend if not self.external_blend else path[0]
        # ET.SubElement(network, "ComponentFile").text = path[1]
        ET.SubElement(network, "IntermediateFile").text = path[2]

        output = ET.SubElement(object, "OutputTagCollection")
        ET.SubElement(output, "OutputTag", Type="render_model").text = self.tag_path

    def write_decorator_contents(self, metadata, sidecar_paths, asset_name, lods):
        contents = ET.SubElement(metadata, "Contents")
        content = ET.SubElement(
            contents, "Content", Name=asset_name, Type="decorator_set"
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

    def write_particle_contents(self, metadata, sidecar_paths, asset_name):
        contents = ET.SubElement(metadata, "Contents")
        content = ET.SubElement(
            contents, "Content", Name=asset_name, Type="particle_model"
        )
        object = ET.SubElement(content, "ContentObject", Name="", Type="particle_model")

        path = sidecar_paths.get("particle_model")[0]

        network = ET.SubElement(object, "ContentNetwork", Name=asset_name, Type="")
        ET.SubElement(network, "InputFile").text = self.relative_blend if not self.external_blend else path[0]
        # ET.SubElement(network, "ComponentFile").text = path[1]
        ET.SubElement(network, "IntermediateFile").text = path[2]

        ET.SubElement(object, "OutputTagCollection")

    def write_prefab_contents(self, metadata, sidecar_paths, asset_name):
        contents = ET.SubElement(metadata, "Contents")
        content = ET.SubElement(contents, "Content", Name=asset_name, Type="prefab")
        object = ET.SubElement(
            content, "ContentObject", Name="", Type="scenario_structure_bsp"
        )

        path = sidecar_paths.get("prefab")[0]

        network = ET.SubElement(object, "ContentNetwork", Name=asset_name, Type="")
        ET.SubElement(network, "InputFile").text = self.relative_blend if not self.external_blend else path[0]
        # ET.SubElement(network, "ComponentFile").text = path[1]
        ET.SubElement(network, "IntermediateFile").text = path[2]

        output = ET.SubElement(object, "OutputTagCollection")
        ET.SubElement(
            output, "OutputTag", Type="scenario_structure_bsp"
        ).text = f"{self.tag_path}"
        ET.SubElement(
            output, "OutputTag", Type="scenario_structure_lighting_info"
        ).text = f"{self.tag_path}"

    def write_fp_animation_contents(
        self, metadata, sidecar_paths, asset_path, asset_name
    ):
        # NULL RENDER
        contents = ET.SubElement(metadata, "Contents")
        content = ET.SubElement(contents, "Content", Name=asset_name, Type="model")
        object = ET.SubElement(content, "ContentObject", Name="", Type="render_model")

        network = ET.SubElement(object, "ContentNetwork", Name="default", Type="")
        ET.SubElement(network, "InputFile").text = self.relative_blend if not self.external_blend else os.path.join(asset_path, asset_name)    
        ET.SubElement(network, "IntermediateFile").text = os.path.join(
            asset_path.replace(get_data_path(), ""),
            "export",
            "models",
            "null_render.gr2",
        )

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
                compression = path[5] if path[5] != "Automatic" else None
                network_attribs = {"Name": path[3], "Type": "Base"}
                match path[4]:
                    case "JMM":
                        network_attribs['ModelAnimationMovementData'] = "None"
                    case "JMA":
                        network_attribs['ModelAnimationMovementData'] = "XY"
                    case "JMT":
                        network_attribs['ModelAnimationMovementData'] = "XYYaw"
                    case "JMZ":
                        network_attribs['ModelAnimationMovementData'] = "XYZYaw"
                    case "JMV":
                        network_attribs['ModelAnimationMovementData'] = "XYZFullRotation"
                    case "JMO":
                        network_attribs['Type'] = "Overlay"
                        network_attribs['ModelAnimationOverlayType'] = "Keyframe"
                        network_attribs['ModelAnimationOverlayBlending'] = "Additive"
                    case "JMOX":
                        network_attribs['Type'] = "Overlay"
                        network_attribs['ModelAnimationOverlayType'] = "Pose"
                        network_attribs['ModelAnimationOverlayBlending'] = "Additive"
                    case "JMR":
                        network_attribs['Type'] = "Overlay"
                        network_attribs['ModelAnimationOverlayType'] = "Keyframe"
                        network_attribs['ModelAnimationOverlayBlending'] = "ReplacementObjectSpace"
                    case _:
                        network_attribs['Type'] = "Overlay"
                        network_attribs['ModelAnimationOverlayType'] = "Keyframe"
                        network_attribs['ModelAnimationOverlayBlending'] = "ReplacementLocalSpace"
                    
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
                        Name=rename.rename_name,
                        Type="Rename",
                        NetworkReference=nwo.name_override,
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
