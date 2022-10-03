# ##### BEGIN MIT LICENSE BLOCK #####
#
# MIT License
#
# Copyright (c) 2022 Generalkidd & Crisp
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

EKPath = bpy.context.preferences.addons['io_scene_halo'].preferences.hrek_path

#clean editing kit path
EKPath = EKPath.replace('"','')
EKPath = EKPath.strip('\\')

valid_animation_types = ('JMM', 'JMA', 'JMT', 'JMZ', 'JMV', 'JMO', 'JMOX', 'JMR', 'JMRX')

special_prefixes = ('b ', 'b_', 'frame ', 'frame_','bip ','bip_','bone ','bone_','#','+soft_ceiling','+soft_kill','+slip_surface', '@','+cookie','+decorator','+flair', '%', '$','+fog','+portal', '+seam','+water', '\'')
bsp_prefixes = ('@', '+cookie', '\'')

def export_xml(report, filePath="", export_sidecar=False, sidecar_type='MODEL', asset_path='',        
                output_biped=False,
                output_crate=False,
                output_creature=False,
                output_device_control=False,
                output_device_machine=False,
                output_device_terminal=False,
                output_effect_scenery=False,
                output_equipment=False,
                output_giant=False,
                output_scenery=False,
                output_vehicle=False,
                output_weapon=False):
    full_path = filePath.rpartition('\\')[0]
    print('full path = ' + filePath)
    asset_path = CleanAssetPath(full_path)
    asset_name = asset_path.rpartition('\\')[2]

    BuildSidecar(asset_path, asset_name, full_path, sidecar_type, output_biped,output_crate,output_creature,output_device_control,output_device_machine,output_device_terminal,output_effect_scenery,output_equipment,output_giant,output_scenery,output_vehicle,output_weapon)

    report({'INFO'},"Sidecar build complete")

def CleanAssetPath(path):
    path = path.replace('"','')
    path = path.strip('\\')
    path = path.replace(EKPath + '\\data\\','')

    return path

def BuildSidecar(asset_path, asset_name, full_path, sidecar_type,               
                        output_biped=False,
                        output_crate=False,
                        output_creature=False,
                        output_device_control=False,
                        output_device_machine=False,
                        output_device_terminal=False,
                        output_effect_scenery=False,
                        output_equipment=False,
                        output_giant=False,
                        output_scenery=False,
                        output_vehicle=False,
                        output_weapon=False, ):

    m_encoding = 'utf-8'
    m_standalone = 'yes'

    metadata = ET.Element("Metadata")
    WriteHeader(metadata)
    if sidecar_type == 'MODEL':
        GetObjectOutputTypes(metadata, "model", asset_path, asset_name, GetModelTags(output_biped,output_crate,output_creature,output_device_control,output_device_machine,output_device_terminal,output_effect_scenery,output_equipment,output_giant,output_scenery,output_vehicle,output_weapon))
    elif sidecar_type == 'SCENARIO':
        GetObjectOutputTypes(metadata, 'scenario', asset_path, asset_name)
    elif sidecar_type == 'DECORATOR SET':
        GetObjectOutputTypes(metadata, 'decorator set', asset_path, asset_name, 'model')
    elif sidecar_type == 'PARTICLE MODEL':
        GetObjectOutputTypes(metadata, 'particle model', asset_path, asset_name, 'model')
    WriteFolders(metadata)
    WriteFaceCollections(metadata, sidecar_type)
    if sidecar_type == 'MODEL':
        WriteModelContents(metadata, asset_path, asset_name)
    if sidecar_type == 'SCENARIO':
        WriteScenarioContents(metadata, asset_path, asset_name)
    # if sidecar_type == 'DECORATOR SET':
    #     WriteDecoratorContents(metadata, asset_path, asset_name)
    # if sidecar_type == 'PARTICLE MODEL':
    #     WriteParticleContents(metadata, asset_path, asset_name)

    dom = xml.dom.minidom.parseString(ET.tostring(metadata))
    xml_string = dom.toprettyxml(indent='  ')
    part1, part2 = xml_string.split('?>')

    with open(full_path + '\\' + asset_name + '.sidecar.xml', 'w') as xfile:
        xfile.write(part1 + 'encoding=\"{}\" standalone=\"{}\"?>'.format(m_encoding, m_standalone) + part2)
        xfile.close()

def WriteHeader(metadata):
    header = ET.SubElement(metadata, "Header")
    ET.SubElement(header, "MainRev").text = "0"
    ET.SubElement(header, "PointRev").text = "6"
    ET.SubElement(header, "Description").text = "Created using the Halo Blender Toolset"
    ET.SubElement(header, "Created").text = str(datetime.today().strftime('%Y-%m-%d %H:%M:%S'))
    ET.SubElement(header, "By").text = getpass.getuser()
    ET.SubElement(header, "DirectoryType").text = "TAE.Shared.NWOAssetDirectory"
    ET.SubElement(header, "Schema").text = "1"

def GetModelTags(       output_biped=False,
                        output_crate=False,
                        output_creature=False,
                        output_device_control=False,
                        output_device_machine=False,
                        output_device_terminal=False,
                        output_effect_scenery=False,
                        output_equipment=False,
                        output_giant=False,
                        output_scenery=False,
                        output_vehicle=False,
                        output_weapon=False):
    
    tags = ['model']

    if output_biped: 
        tags.append('biped')
    if output_crate:
        tags.append('crate')
    if output_creature:
        tags.append('creature')
    if output_device_control:
        tags.append('device_control')
    if output_device_machine:
        tags.append('device_machine')
    if output_device_terminal:
        tags.append('device_terminal')
    if output_effect_scenery:
        tags.append('effect_scenery')
    if output_equipment:
        tags.append('equipment')
    if output_giant:
        tags.append('giant')
    if output_scenery:
        tags.append('scenery')
    if output_vehicle:
        tags.append('vehicle')
    if output_weapon:
        tags.append('weapon')

    return tags

def GetObjectOutputTypes(metadata, type, asset_path, asset_name, output_tags=[]):
    
    asset = ET.SubElement(metadata, "Asset", Name=asset_name, Type=type)
    tagcollection = ET.SubElement(asset, "OutputTagCollection")

    if type == 'model':
        for tag in output_tags:
            ET.SubElement(tagcollection, "OutputTag", Type=tag).text = asset_path + '\\' + asset_name

    elif type == 'scenario':
        ET.SubElement(tagcollection, "OutputTag", Type='scenario_lightmap').text = asset_path + '\\' + asset_name + '_faux_lightmaps'
        ET.SubElement(tagcollection, "OutputTag", Type='structure_seams').text = asset_path + '\\' + asset_name
        ET.SubElement(tagcollection, "OutputTag", Type='scenario').text = asset_path + '\\' + asset_name

def WriteFolders(metadata):
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
    ET.SubElement(folders, "Scripts").text = "\\scripts"

def WriteFaceCollections(metadata, sidecar_type):
        faceCollections = ET.SubElement(metadata, "FaceCollections")

        if(sidecar_type == 'MODEL'):
            region_list = ["default",""]
            f1 = ET.SubElement(faceCollections, "FaceCollection", Name="regions", StringTable="connected_geometry_regions_table", Description="Model regions")

            FaceCollectionsEntries = ET.SubElement(f1, "FaceCollectionEntries")
            ET.SubElement(FaceCollectionsEntries, "FaceCollectionEntry", Index="0", Name="default", Active="true")

            count = 1
            for ob in bpy.data.objects:
                region = ob.halo_json.Region_Name
                if region not in region_list:
                    ET.SubElement(FaceCollectionsEntries, "FaceCollectionEntry", Index=str(count), Name=region, Active="true")
                    region_list.append(region)
                    count += 1
        if(sidecar_type == 'MODEL' or sidecar_type == 'SCENARIO'):
            mat_list = ["default",""]
            f2 = ET.SubElement(faceCollections, "FaceCollection", Name="global materials override", StringTable="connected_geometry_global_material_table", Description="Global material overrides")

            FaceCollectionsEntries2 = ET.SubElement(f2, "FaceCollectionEntries")
            ET.SubElement(FaceCollectionsEntries2, "FaceCollectionEntry", Index="0", Name="default", Active="true")

            count = 1
            for ob in bpy.data.objects:
                material = ob.halo_json.Face_Global_Material
                if material not in mat_list:
                        ET.SubElement(FaceCollectionsEntries2, "FaceCollectionEntry", Index=str(count), Name=material, Active="true")
                        mat_list.append(material)
                        count += 1

def WriteModelContents(metadata, asset_path, asset_name):
    ##### RENDER #####
    contents = ET.SubElement(metadata, "Contents")
    content = ET.SubElement(contents, "Content", Name=asset_name, Type='model')
    object = ET.SubElement(content, 'ContentObject', Name='', Type="render_model")

    perm_list = []
    for ob in bpy.data.objects:
        if ob.halo_json.Permutation_Name == '':
            perm = 'default'
        else:
            perm = ob.halo_json.Permutation_Name
        if (perm not in perm_list) and RenderPermExists():
            perm_list.append(perm)
            network = ET.SubElement(object, 'ContentNetwork' ,Name=perm, Type="")
            ET.SubElement(network, 'InputFile').text = GetInputFilePath(asset_path, asset_name, 'render', ob.halo_json.Permutation_Name)
            ET.SubElement(network, 'IntermediateFile').text = GetIntermediateFilePath(asset_path, asset_name, 'render', ob.halo_json.Permutation_Name)

    output = ET.SubElement(object, 'OutputTagCollection')
    ET.SubElement(output, 'OutputTag', Type='render_model').text = asset_path + '\\' + asset_name

    ##### PHYSICS #####
    if SceneHasPhysicsObject():
        object = ET.SubElement(content, 'ContentObject', Name='', Type="physics_model")

        perm_list = []
        for ob in bpy.data.objects:
            if ob.halo_json.Permutation_Name == '':
                perm = 'default'
            else:
                perm = ob.halo_json.Permutation_Name
            if (perm not in perm_list) and PhysicsPermExists():
                perm_list.append(perm)
                network = ET.SubElement(object, 'ContentNetwork' ,Name=perm, Type="")
                ET.SubElement(network, 'InputFile').text = GetInputFilePath(asset_path, asset_name, 'physics', ob.halo_json.Permutation_Name)
                ET.SubElement(network, 'IntermediateFile').text = GetIntermediateFilePath(asset_path, asset_name, 'physics', ob.halo_json.Permutation_Name)

        output = ET.SubElement(object, 'OutputTagCollection')
        ET.SubElement(output, 'OutputTag', Type='physics_model').text = asset_path + '\\' + asset_name

    ##### COLLISION #####    
    if SceneHasCollisionObject():
        object = ET.SubElement(content, 'ContentObject', Name='', Type="collision_model")

        perm_list = []
        for ob in bpy.data.objects:
            if ob.halo_json.Permutation_Name == '':
                perm = 'default'
            else:
                perm = ob.halo_json.Permutation_Name
            if (perm not in perm_list) and CollisionPermExists():
                perm_list.append(perm)
                network = ET.SubElement(object, 'ContentNetwork' ,Name=perm, Type="")
                ET.SubElement(network, 'InputFile').text = GetInputFilePath(asset_path, asset_name, 'collision', ob.halo_json.Permutation_Name)
                ET.SubElement(network, 'IntermediateFile').text = GetIntermediateFilePath(asset_path, asset_name, 'collision', ob.halo_json.Permutation_Name)

        output = ET.SubElement(object, 'OutputTagCollection')
        ET.SubElement(output, 'OutputTag', Type='collision_model').text = asset_path + '\\' + asset_name

    ##### SKELETON #####
    object = ET.SubElement(content, 'ContentObject', Name='', Type="skeleton")
    network = ET.SubElement(object, 'ContentNetwork' , Name='default', Type="")
    ET.SubElement(network, 'InputFile').text = GetInputFilePath(asset_path, asset_name, 'skeleton')
    ET.SubElement(network, 'IntermediateFile').text = GetIntermediateFilePath(asset_path, asset_name, 'skeleton')

    output = ET.SubElement(object, 'OutputTagCollection')
    
    ##### MARKERS #####
    if SceneHasMarkers():
        object = ET.SubElement(content, 'ContentObject', Name='', Type="markers")
        network = ET.SubElement(object, 'ContentNetwork' , Name='default', Type="")
        ET.SubElement(network, 'InputFile').text = GetInputFilePath(asset_path, asset_name, 'markers')
        ET.SubElement(network, 'IntermediateFile').text = GetIntermediateFilePath(asset_path, asset_name, 'markers')
        
        output = ET.SubElement(object, 'OutputTagCollection')

    ##### ANIMATIONS #####
    if 1<=len(bpy.data.actions):
        object = ET.SubElement(content, 'ContentObject', Name='', Type="model_animation_graph")

        for anim in bpy.data.actions:
            if anim.name.rpartition('.')[0] != '':
                anim_name = anim.name.rpartition('.')[0]
                anim_type = anim.name.rpartition('.')[2]
                anim_type = anim_type.upper()
            else:
                anim_name = anim.name
                anim_type = 'JMM'
            
            if anim_type not in valid_animation_types:
                anim_type = 'JMM'
            
            match anim_type:
                case 'JMM':
                    network = ET.SubElement(object, 'ContentNetwork' , Name=anim_name, Type='Base', ModelAnimationMovementData='None')
                case 'JMA':
                    network = ET.SubElement(object, 'ContentNetwork' , Name=anim_name, Type='Base', ModelAnimationMovementData='XY')
                case 'JMT':
                    network = ET.SubElement(object, 'ContentNetwork' , Name=anim_name, Type='Base', ModelAnimationMovementData='XYYaw')
                case 'JMZ':
                    network = ET.SubElement(object, 'ContentNetwork' , Name=anim_name, Type='Base', ModelAnimationMovementData='XYZYaw')
                case 'JMV':
                    network = ET.SubElement(object, 'ContentNetwork' , Name=anim_name, Type='Base', ModelAnimationMovementData='XYZFullRotation')
                case 'JMO':
                    network = ET.SubElement(object, 'ContentNetwork' , Name=anim_name, Type='Overlay', ModelAnimationOverlayType='Keyframe', ModelAnimationOverlayBlending='Additive')
                case 'JMOX':
                    network = ET.SubElement(object, 'ContentNetwork' , Name=anim_name, Type='Overlay', ModelAnimationOverlayType='Pose', ModelAnimationOverlayBlending='Additive')
                case 'JMR':
                    network = ET.SubElement(object, 'ContentNetwork' , Name=anim_name, Type='Overlay', ModelAnimationOverlayType='Keyframe', ModelAnimationOverlayBlending='ReplacementObjectSpace')
                case _:
                    network = ET.SubElement(object, 'ContentNetwork' , Name=anim_name, Type='Overlay', ModelAnimationOverlayType='Keyframe', ModelAnimationOverlayBlending='ReplacementLocalSpace')

            ET.SubElement(network, 'InputFile').text = GetInputFilePath(asset_path, anim_name, 'model_animation_graph')
            ET.SubElement(network, 'IntermediateFile').text = GetIntermediateFilePath(asset_path, anim_name, 'model_animation_graph')

        output = ET.SubElement(object, 'OutputTagCollection')
        ET.SubElement(output, 'OutputTag', Type='frame_event_list').text = asset_path + '\\' + asset_name
        ET.SubElement(output, 'OutputTag', Type='model_animation_graph').text = asset_path + '\\' + asset_name

def WriteScenarioContents(metadata, asset_path, asset_name):
    contents = ET.SubElement(metadata, "Contents")
    ##### STRUCTURE #####
    if SceneHasBSP():
        bsp_list = []
        shared_bsp_exists = False

        for ob in bpy.data.objects:
            if not ob.halo_json.bsp_shared and (ob.halo_json.bsp_index not in bsp_list):
                bsp_list.append(ob.halo_json.bsp_index)

        for ob in bpy.data.objects:
            if ob.halo_json.bsp_shared:
                shared_bsp_exists = True
                break

        shared_structure_perm = []
        shared_poop_perm = []
        shared_marker_perm = []
        shared_light_perm = []
        shared_portal_perm = []
        shared_seam_perm = []
        shared_water_perm = []
        shared_lightmap_perm = []
        shared_fog_perm = []
        shared_cookie_perm = []

        if shared_bsp_exists:
            for ob in bpy.data.objects:
                if IsStructure(ob) and ob.halo_json.bsp_shared:
                    if ob.halo_json.Permutation_Name == '':
                        perm = 'default'
                    else:
                        perm = ob.halo_json.Permutation_Name
                    if (perm not in shared_structure_perm):
                        shared_structure_perm.append(perm)

                elif IsPoop(ob) and ob.halo_json.bsp_shared:
                    if ob.halo_json.Permutation_Name == '':
                        perm = 'default'
                    else:
                        perm = ob.halo_json.Permutation_Name
                    if (perm not in shared_poop_perm):
                        shared_poop_perm.append(perm)

                elif IsMarker(ob) and ob.halo_json.bsp_shared:
                    if ob.halo_json.Permutation_Name == '':
                        perm = 'default'
                    else:
                        perm = ob.halo_json.Permutation_Name
                    if (perm not in shared_marker_perm):
                        shared_marker_perm.append(perm)

                elif IsLight(ob) and ob.halo_json.bsp_shared:
                    if ob.halo_json.Permutation_Name == '':
                        perm = 'default'
                    else:
                        perm = ob.halo_json.Permutation_Name
                    if (perm not in shared_light_perm):
                        shared_light_perm.append(perm)

                elif IsPortal(ob) and ob.halo_json.bsp_shared:
                    if ob.halo_json.Permutation_Name == '':
                        perm = 'default'
                    else:
                        perm = ob.halo_json.Permutation_Name
                    if (perm not in shared_portal_perm):
                        shared_portal_perm.append(perm)

                elif IsSeam(ob) and ob.halo_json.bsp_shared:
                    if ob.halo_json.Permutation_Name == '':
                        perm = 'default'
                    else:
                        perm = ob.halo_json.Permutation_Name
                    if (perm not in shared_seam_perm):
                        shared_seam_perm.append(perm)

                elif IsWaterSurface(ob) and ob.halo_json.bsp_shared:
                    if ob.halo_json.Permutation_Name == '':
                        perm = 'default'
                    else:
                        perm = ob.halo_json.Permutation_Name
                    if (perm not in shared_water_perm):
                        shared_water_perm.append(perm)

                elif IsLightMapRegion(ob) and ob.halo_json.bsp_shared:
                    if ob.halo_json.Permutation_Name == '':
                        perm = 'default'
                    else:
                        perm = ob.halo_json.Permutation_Name
                    if (perm not in shared_lightmap_perm):
                        shared_lightmap_perm.append(perm)

                elif IsFog(ob) and ob.halo_json.bsp_shared:
                    if ob.halo_json.Permutation_Name == '':
                        perm = 'default'
                    else:
                        perm = ob.halo_json.Permutation_Name
                    if (perm not in shared_fog_perm):
                        shared_fog_perm.append(perm)

                elif IsCookie(ob) and ob.halo_json.bsp_shared:
                    if ob.halo_json.Permutation_Name == '':
                        perm = 'default'
                    else:
                        perm = ob.halo_json.Permutation_Name
                    if (perm not in shared_cookie_perm):
                        shared_cookie_perm.append(perm)

        for bsp in bsp_list:
            content = ET.SubElement(contents, "Content", Name=asset_name + '_' + "{0:03}".format(bsp), Type='bsp', BspErrorPolicy='auto_generated_physics')
            object = ET.SubElement(content, 'ContentObject', Name='', Type="scenario_structure_bsp")
            structure_perm = []
            poop_perm = []
            marker_perm = []
            light_perm = []
            portal_perm = []
            seam_perm = []
            water_perm = []
            lightmap_perm = []
            fog_perm = []
            cookie_perm = []
            for ob in bpy.data.objects:
                if IsStructure(ob) and ob.halo_json.bsp_index == bsp:
                    if ob.halo_json.Permutation_Name == '':
                        perm = 'default'
                    else:
                        perm = ob.halo_json.Permutation_Name
                    if (perm not in structure_perm):
                        structure_perm.append(perm)

                elif IsPoop(ob) and ob.halo_json.bsp_index == bsp:
                    if ob.halo_json.Permutation_Name == '':
                        perm = 'default'
                    else:
                        perm = ob.halo_json.Permutation_Name
                    if (perm not in poop_perm):
                        poop_perm.append(perm)

                elif IsMarker(ob) and ob.halo_json.bsp_index == bsp:
                    if ob.halo_json.Permutation_Name == '':
                        perm = 'default'
                    else:
                        perm = ob.halo_json.Permutation_Name
                    if (perm not in marker_perm):
                        marker_perm.append(perm)

                elif IsLight(ob) and ob.halo_json.bsp_index == bsp:
                    if ob.halo_json.Permutation_Name == '':
                        perm = 'default'
                    else:
                        perm = ob.halo_json.Permutation_Name
                    if (perm not in light_perm):
                        light_perm.append(perm)

                elif IsPortal(ob) and ob.halo_json.bsp_index == bsp:
                    if ob.halo_json.Permutation_Name == '':
                        perm = 'default'
                    else:
                        perm = ob.halo_json.Permutation_Name
                    if (perm not in portal_perm):
                        portal_perm.append(perm)

                elif IsSeam(ob) and ob.halo_json.bsp_index == bsp:
                    if ob.halo_json.Permutation_Name == '':
                        perm = 'default'
                    else:
                        perm = ob.halo_json.Permutation_Name
                    if (perm not in seam_perm):
                        seam_perm.append(perm)

                elif IsWaterSurface(ob) and ob.halo_json.bsp_index == bsp:
                    if ob.halo_json.Permutation_Name == '':
                        perm = 'default'
                    else:
                        perm = ob.halo_json.Permutation_Name
                    if (perm not in water_perm):
                        water_perm.append(perm)

                elif IsLightMapRegion(ob) and ob.halo_json.bsp_index == bsp:
                    if ob.halo_json.Permutation_Name == '':
                        perm = 'default'
                    else:
                        perm = ob.halo_json.Permutation_Name
                    if (perm not in lightmap_perm):
                        lightmap_perm.append(perm)

                elif IsFog(ob) and ob.halo_json.bsp_index == bsp:
                    if ob.halo_json.Permutation_Name == '':
                        perm = 'default'
                    else:
                        perm = ob.halo_json.Permutation_Name
                    if (perm not in fog_perm):
                        fog_perm.append(perm)

                elif IsCookie(ob) and ob.halo_json.bsp_index == bsp:
                    if ob.halo_json.Permutation_Name == '':
                        perm = 'default'
                    else:
                        perm = ob.halo_json.Permutation_Name
                    if (perm not in cookie_perm):
                        cookie_perm.append(perm)

            for perm in structure_perm:
                network = ET.SubElement(object, 'ContentNetwork' ,Name=asset_name + '_' + "{0:03}".format(bsp) + perm + '_' + 'structure', Type="")
                ET.SubElement(network, 'InputFile').text = GetInputFilePathBSP(asset_path, asset_name, "{0:03}".format(bsp), 'structure', perm)
                ET.SubElement(network, 'IntermediateFile').text = GetIntermediateFilePathBSP(asset_path, asset_name, "{0:03}".format(bsp), 'structure', perm)
            for perm in poop_perm:
                network = ET.SubElement(object, 'ContentNetwork' ,Name=asset_name + '_' + "{0:03}".format(bsp) + '_' + perm + '_' + 'poops', Type="")
                ET.SubElement(network, 'InputFile').text = GetInputFilePathBSP(asset_path, asset_name,  "{0:03}".format(bsp), 'poops', perm)
                ET.SubElement(network, 'IntermediateFile').text = GetIntermediateFilePathBSP(asset_path, asset_name, "{0:03}".format(bsp), 'poops', perm)
            for perm in marker_perm:
                network = ET.SubElement(object, 'ContentNetwork' ,Name=asset_name + '_' + "{0:03}".format(bsp) + '_' + perm + '_' + 'markers', Type="")
                ET.SubElement(network, 'InputFile').text = GetInputFilePathBSP(asset_path, asset_name, "{0:03}".format(bsp), 'markers', perm)
                ET.SubElement(network, 'IntermediateFile').text = GetIntermediateFilePathBSP(asset_path, asset_name, "{0:03}".format(bsp), 'markers', perm)
            for perm in light_perm:
                network = ET.SubElement(object, 'ContentNetwork' ,Name=asset_name + '_' + "{0:03}".format(bsp) + '_' + perm + '_' + 'lights', Type="")
                ET.SubElement(network, 'InputFile').text = GetInputFilePathBSP(asset_path, asset_name, "{0:03}".format(bsp), 'lights', perm)
                ET.SubElement(network, 'IntermediateFile').text = GetIntermediateFilePathBSP(asset_path, asset_name, "{0:03}".format(bsp), 'lights', perm)
            for perm in portal_perm:
                network = ET.SubElement(object, 'ContentNetwork' ,Name=asset_name + '_' + "{0:03}".format(bsp) + '_' + perm + '_' + 'portals', Type="")
                ET.SubElement(network, 'InputFile').text = GetInputFilePathBSP(asset_path, asset_name, "{0:03}".format(bsp), 'portals', perm)
                ET.SubElement(network, 'IntermediateFile').text = GetIntermediateFilePathBSP(asset_path, asset_name, "{0:03}".format(bsp), 'portals', perm)
            for perm in seam_perm:
                network = ET.SubElement(object, 'ContentNetwork' ,Name=asset_name + '_' + "{0:03}".format(bsp) + '_' + perm + '_' + 'seams', Type="")
                ET.SubElement(network, 'InputFile').text = GetInputFilePathBSP(asset_path, asset_name, "{0:03}".format(bsp), 'seams', perm)
                ET.SubElement(network, 'IntermediateFile').text = GetIntermediateFilePathBSP(asset_path, asset_name, "{0:03}".format(bsp), 'seams', perm)
            for perm in water_perm:
                network = ET.SubElement(object, 'ContentNetwork' ,Name=asset_name + '_' + "{0:03}".format(bsp) + '_' + perm + '_' + 'water', Type="")
                ET.SubElement(network, 'InputFile').text = GetInputFilePathBSP(asset_path, asset_name, "{0:03}".format(bsp), 'water', perm)
                ET.SubElement(network, 'IntermediateFile').text = GetIntermediateFilePathBSP(asset_path, asset_name, "{0:03}".format(bsp), 'water', perm)
            for perm in lightmap_perm:
                network = ET.SubElement(object, 'ContentNetwork' ,Name=asset_name + '_' + "{0:03}".format(bsp) + '_' + perm + '_' + 'lightmap_region', Type="")
                ET.SubElement(network, 'InputFile').text = GetInputFilePathBSP(asset_path, asset_name, "{0:03}".format(bsp), 'lightmap_region', perm)
                ET.SubElement(network, 'IntermediateFile').text = GetIntermediateFilePathBSP(asset_path, asset_name, "{0:03}".format(bsp), 'lightmap_region', perm)
            for perm in fog_perm:
                network = ET.SubElement(object, 'ContentNetwork' ,Name=asset_name + '_' + "{0:03}".format(bsp) + '_' + perm + '_' + 'fog', Type="")
                ET.SubElement(network, 'InputFile').text = GetInputFilePathBSP(asset_path, asset_name, "{0:03}".format(bsp), 'fog', perm)
                ET.SubElement(network, 'IntermediateFile').text = GetIntermediateFilePathBSP(asset_path, asset_name, "{0:03}".format(bsp), 'fog', perm)
            for perm in cookie_perm:
                network = ET.SubElement(object, 'ContentNetwork' ,Name=asset_name + '_' + "{0:03}".format(bsp) + '_' + perm + '_' + 'cookie_cutters', Type="")
                ET.SubElement(network, 'InputFile').text = GetInputFilePathBSP(asset_path, asset_name, "{0:03}".format(bsp), 'cookie_cutters', perm)
                ET.SubElement(network, 'IntermediateFile').text = GetIntermediateFilePathBSP(asset_path, asset_name, "{0:03}".format(bsp), 'cookie_cutters', perm)

            for perm in shared_structure_perm:
                network = ET.SubElement(object, 'ContentNetwork' ,Name=asset_name + '_' + 'shared' + '_' + perm + '_' + 'bsp', Type="")
                ET.SubElement(network, 'InputFile').text = GetInputFilePathBSP(asset_path, asset_name, 'shared', 'bsp', perm)
                ET.SubElement(network, 'IntermediateFile').text = GetIntermediateFilePathBSP(asset_path, asset_name, 'shared', 'bsp', perm)
            for perm in shared_poop_perm:
                network = ET.SubElement(object, 'ContentNetwork' ,Name=asset_name + '_' + 'shared' + '_' + perm + '_' + 'poops', Type="")
                ET.SubElement(network, 'InputFile').text = GetInputFilePathBSP(asset_path, asset_name,  'shared', 'poops', perm)
                ET.SubElement(network, 'IntermediateFile').text = GetIntermediateFilePathBSP(asset_path, asset_name, 'shared', 'poops', perm)
            for perm in shared_marker_perm:
                network = ET.SubElement(object, 'ContentNetwork' ,Name=asset_name + '_' + 'shared' + '_' + perm + '_' + 'markers', Type="")
                ET.SubElement(network, 'InputFile').text = GetInputFilePathBSP(asset_path, asset_name, 'shared', 'markers', perm)
                ET.SubElement(network, 'IntermediateFile').text = GetIntermediateFilePathBSP(asset_path, asset_name, 'shared', 'markers', perm)
            for perm in shared_light_perm:
                network = ET.SubElement(object, 'ContentNetwork' ,Name=asset_name + '_' + 'shared' + '_' + perm + '_' + 'lights', Type="")
                ET.SubElement(network, 'InputFile').text = GetInputFilePathBSP(asset_path, asset_name, 'shared', 'lights', perm)
                ET.SubElement(network, 'IntermediateFile').text = GetIntermediateFilePathBSP(asset_path, asset_name, 'shared', 'lights', perm)
            for perm in shared_portal_perm:
                network = ET.SubElement(object, 'ContentNetwork' ,Name=asset_name + '_' + 'shared' + '_' + perm + '_' + 'portals', Type="")
                ET.SubElement(network, 'InputFile').text = GetInputFilePathBSP(asset_path, asset_name, 'shared', 'portals', perm)
                ET.SubElement(network, 'IntermediateFile').text = GetIntermediateFilePathBSP(asset_path, asset_name, 'shared', 'portals', perm)
            for perm in shared_seam_perm:
                network = ET.SubElement(object, 'ContentNetwork' ,Name=asset_name + '_' + 'shared' + '_' + perm + '_' + 'seams', Type="")
                ET.SubElement(network, 'InputFile').text = GetInputFilePathBSP(asset_path, asset_name, 'shared', 'seams', perm)
                ET.SubElement(network, 'IntermediateFile').text = GetIntermediateFilePathBSP(asset_path, asset_name, 'shared', 'seams', perm)
            for perm in shared_water_perm:
                network = ET.SubElement(object, 'ContentNetwork' ,Name=asset_name + '_' + 'shared' + '_' + perm + '_' + 'water', Type="")
                ET.SubElement(network, 'InputFile').text = GetInputFilePathBSP(asset_path, asset_name, 'shared', 'water', perm)
                ET.SubElement(network, 'IntermediateFile').text = GetIntermediateFilePathBSP(asset_path, asset_name, 'shared', 'water', perm)
            for perm in shared_lightmap_perm:
                network = ET.SubElement(object, 'ContentNetwork' ,Name=asset_name + '_' + 'shared' + '_' + perm + '_' + 'lightmap_region', Type="")
                ET.SubElement(network, 'InputFile').text = GetInputFilePathBSP(asset_path, asset_name, 'shared', 'lightmap_region', perm)
                ET.SubElement(network, 'IntermediateFile').text = GetIntermediateFilePathBSP(asset_path, asset_name, 'shared', 'lightmap_region', perm)
            for perm in shared_fog_perm:
                network = ET.SubElement(object, 'ContentNetwork' ,Name=asset_name + '_' + 'shared' + '_' + perm + '_' + 'fog', Type="")
                ET.SubElement(network, 'InputFile').text = GetInputFilePathBSP(asset_path, asset_name, 'shared', 'fog', perm)
                ET.SubElement(network, 'IntermediateFile').text = GetIntermediateFilePathBSP(asset_path, asset_name, 'shared', 'fog', perm)
            for perm in shared_cookie_perm:
                network = ET.SubElement(object, 'ContentNetwork' ,Name=asset_name + '_' + 'shared' + '_' + perm + '_' + 'cookie_cutters', Type="")
                ET.SubElement(network, 'InputFile').text = GetInputFilePathBSP(asset_path, asset_name, 'shared', 'cookie_cutters', perm)
                ET.SubElement(network, 'IntermediateFile').text = GetIntermediateFilePathBSP(asset_path, asset_name, 'shared', 'cookie_cutters', perm)

            output = ET.SubElement(object, 'OutputTagCollection')
            ET.SubElement(output, 'OutputTag', Type='scenario_structure_bsp').text = asset_path + '\\' + asset_name + '_' + "{0:03}".format(bsp)
            ET.SubElement(output, 'OutputTag', Type='scenario_structure_lighting_info').text = asset_path + '\\' + asset_name + '_' + "{0:03}".format(bsp)
        
    ##### STRUCTURE DESIGN #####
    if SceneHasDesign():
        bsp_list = []
        shared_bsp_exists = False

        for ob in bpy.data.objects:
            if not ob.halo_json.bsp_shared and (ob.halo_json.bsp_index not in bsp_list) and (IsBoundary(ob) or IsWaterPhysics(ob) or IsPoopRain(ob)):
                bsp_list.append(ob.halo_json.bsp_index)

        for ob in bpy.data.objects:
            if ob.halo_json.bsp_shared:
                shared_bsp_exists = True
                break
        
        shared_boundary_exists = False
        shared_water_physics_exists = False
        shared_rain_exists = False

        if shared_bsp_exists:
            for ob in bpy.data.objects:
                if IsBoundary(ob) and ob.halo_json.bsp_shared:
                    shared_boundary_exists = True

                elif IsWaterPhysics(ob) and ob.halo_json.bsp_shared:
                    shared_water_physics_exists = True

                elif IsPoopRain(ob) and ob.halo_json.bsp_shared:
                    shared_rain_exists = True
        
        for bsp in bsp_list:
            content = ET.SubElement(contents, "Content", Name=asset_name + '_' + "{0:03}".format(bsp) + '_structure_design', Type='design')
            object = ET.SubElement(content, 'ContentObject', Name='', Type="structure_design")
            boundary_exists = False
            water_physics_exists = False
            rain_exists = False
            for ob in bpy.data.objects:
                if IsBoundary(ob) and ob.halo_json.bsp_index == bsp:
                    boundary_exists = True
                elif IsWaterPhysics(ob) and ob.halo_json.bsp_index == bsp:
                    water_physics_exists = True
                
                elif IsPoopRain(ob) and ob.halo_json.bsp_index == bsp:
                    rain_exists = True

            if boundary_exists:
                network = ET.SubElement(object, 'ContentNetwork' ,Name=asset_name + '_' + "{0:03}".format(bsp) + '_' + 'design', Type="")
                ET.SubElement(network, 'InputFile').text = GetInputFilePathBSP(asset_path, asset_name, "{0:03}".format(bsp), 'design')
                ET.SubElement(network, 'IntermediateFile').text = GetIntermediateFilePathBSP(asset_path, asset_name, "{0:03}".format(bsp), 'design')
            
            if water_physics_exists:
                network = ET.SubElement(object, 'ContentNetwork' ,Name=asset_name + '_' + "{0:03}".format(bsp) + '_' + 'water_physics', Type="")
                ET.SubElement(network, 'InputFile').text = GetInputFilePathBSP(asset_path, asset_name, "{0:03}".format(bsp), 'water_physics')
                ET.SubElement(network, 'IntermediateFile').text = GetIntermediateFilePathBSP(asset_path, asset_name, "{0:03}".format(bsp), 'water_physics')

            if rain_exists:
                network = ET.SubElement(object, 'ContentNetwork' ,Name=asset_name + '_' + "{0:03}".format(bsp) + '_' + 'rain_blockers', Type="")
                ET.SubElement(network, 'InputFile').text = GetInputFilePathBSP(asset_path, asset_name, "{0:03}".format(bsp), 'rain_blockers')
                ET.SubElement(network, 'IntermediateFile').text = GetIntermediateFilePathBSP(asset_path, asset_name, "{0:03}".format(bsp), 'rain_blockers')

            if shared_boundary_exists:
                network = ET.SubElement(object, 'ContentNetwork' ,Name=asset_name + '_' + "{0:03}".format(bsp) + '_' + 'design', Type="")
                ET.SubElement(network, 'InputFile').text = GetInputFilePathBSP(asset_path, asset_name, 'shared', 'design')
                ET.SubElement(network, 'IntermediateFile').text = GetIntermediateFilePathBSP(asset_path, asset_name, 'shared', 'design')

            if shared_water_physics_exists:
                network = ET.SubElement(object, 'ContentNetwork' ,Name=asset_name + '_' + "{0:03}".format(bsp) + '_' + 'water_physics', Type="")
                ET.SubElement(network, 'InputFile').text = GetInputFilePathBSP(asset_path, asset_name, 'shared', 'water_physics')
                ET.SubElement(network, 'IntermediateFile').text = GetIntermediateFilePathBSP(asset_path, asset_name, 'shared', 'water_physics')

            if shared_rain_exists:
                network = ET.SubElement(object, 'ContentNetwork' ,Name=asset_name + '_' + "{0:03}".format(bsp) + '_' + 'rain_blockers', Type="")
                ET.SubElement(network, 'InputFile').text = GetInputFilePathBSP(asset_path, asset_name, 'shared', 'rain_blockers')
                ET.SubElement(network, 'IntermediateFile').text = GetIntermediateFilePathBSP(asset_path, asset_name, 'shared', 'rain_blockers')

            output = ET.SubElement(object, 'OutputTagCollection')
            ET.SubElement(output, 'OutputTag', Type='structure_design').text = asset_path + '\\' + asset_name + '_' + "{0:03}".format(bsp) + '_structure_design'

def GetInputFilePathBSP(asset_path, asset_name, bsp, type, perm=''):
    if perm == '' or perm == 'default':
        path = asset_path + '\\models\\' + asset_name + '_' + bsp + '_' + type + '.fbx'
    else:
        path = asset_path + '\\models\\' + asset_name + '_' + bsp + '_' + type + '_' + perm + '.fbx'

    return path

def GetIntermediateFilePathBSP(asset_path, asset_name, bsp, type, perm=''):
    if perm == '' or perm == 'default':
        path = asset_path + '\\export\\models\\' + asset_name + '_' + bsp + '_' + type + '.gr2'
    else:
        path = asset_path + '\\export\\models\\' + asset_name + '_' + bsp + '_' + type + '_' + perm + '.gr2'

    return path

def SceneHasBSP():
    for ob in bpy.data.objects:
        if IsStructure(ob):
            return True

    return False

def IsStructure(ob):
    return (ob.name.startswith('@') and not ob.parent.name.startswith('%')) or (not ob.name.startswith(special_prefixes) and (ob.halo_json.ObjectMesh_Type == 'COLLISION' or ob.halo_json.ObjectMesh_Type == 'DEFAULT' or ob.halo_json.ObjectMesh_Type == 'LIGHTMAP REGION' ))

def IsPoop(ob):
    return ob.name.startswith('%') or (ob.name.startswith('@') and ob.parent.name.startswith('%')) or (ob.name.startswith('$') and ob.parent.name.startswith('%')) or (not ob.name.startswith(special_prefixes) and (ob.halo_json.ObjectMesh_Type == 'INSTANCED GEOMETRY' or ob.halo_json.ObjectMesh_Type == 'INSTANCED GEOMETRY COLLISION' or ob.halo_json.ObjectMesh_Type == 'INSTANCED GEOMETRY MARKER' or ob.halo_json.ObjectMesh_Type == 'INSTANCED GEOMETRY PHYSICS' or ob.halo_json.ObjectMesh_Type == 'COOKIE CUTTER'))

def IsMarker(ob):
    return ob.name.startswith('#') or ob.halo_json.Object_Type_All == 'MARKER' or (ob.halo_json.Object_Type_No_Mesh == 'MARKER' and ob.type == 'EMPTY')

def IsLight(ob):
    return ob.type == 'LIGHT'

def IsPortal(ob):
    return ob.name.startswith('+portal') or (not ob.name.startswith(special_prefixes) and ob.halo_json.ObjectMesh_Type == 'PORTAL')

def IsSeam(ob):
    return ob.name.startswith('+seam') or (not ob.name.startswith(special_prefixes) and ob.halo_json.ObjectMesh_Type == 'SEAM')

def IsWaterSurface(ob):
    return ob.name.startswith('\'') or (not ob.name.startswith(special_prefixes) and ob.halo_json.ObjectMesh_Type == 'WATER SURFACE')

def IsLightMapRegion(ob):
    return (not ob.name.startswith(special_prefixes) and ob.halo_json.ObjectMesh_Type == 'LIGHTMAP REGION')

def IsFog(ob):
    return ob.name.startswith('+fog') or (not ob.name.startswith(special_prefixes) and (ob.halo_json.ObjectMesh_Type == 'PLANAR FOG VOLUME'))

def IsCookie(ob):
    return ob.name.startswith('+cookie') or (not ob.name.startswith(special_prefixes) and (ob.halo_json.ObjectMesh_Type == 'COOKIE CUTTER'))

def SceneHasDesign():
    for ob in bpy.data.objects:
        if IsBoundary(ob) or IsWaterPhysics(ob) or IsPoopRain(ob):
            return True
    
    return False

def IsBoundary(ob):
    return ob.name.startswith(('+soft_kill', '+soft_ceiling', '+slip_surface')) or (not ob.name.startswith(special_prefixes) and ob.halo_json.ObjectMesh_Type == 'BOUNDARY SURFACE')

def IsWaterPhysics(ob):
    return ob.name.startswith('+water') or (not ob.name.startswith(special_prefixes) and ob.halo_json.ObjectMesh_Type == 'WATER PHYSICS VOLUME')

def IsPoopRain(ob):
    return not ob.name.startswith(special_prefixes) and (ob.halo_json.ObjectMesh_Type == 'INSTANCED GEOMETRY RAIN BLOCKER' or ob.halo_json.ObjectMesh_Type == 'INSTANCED GEOMETRY VERTICAL RAIN SHEET')

def GetInputFilePath(asset_path, asset_name, type, perm=''):
    if type == 'model_animation_graph':
        path = asset_path + '\\animations\\' + asset_name + '.fbx'
    else:
        if perm == '':
            path = asset_path + '\\models\\' + asset_name  + '_' + type + '.fbx'
        else:
            path = asset_path + '\\models\\' + asset_name + '_'  + perm  + '_' + type + '.fbx'

    return path

def GetIntermediateFilePath(asset_path, asset_name, type, perm=''):
    if type == 'model_animation_graph':
        path = asset_path + '\\export\\animations\\' + asset_name + '.gr2'
    else:
        if perm == '':
            path = asset_path + '\\export\\models\\' + asset_name + '_' + type + '.gr2'
        else:
            path = asset_path + '\\export\\models\\' + asset_name + '_'  + perm  + '_' + type + '.gr2'

    return path

def SceneHasCollisionObject():
    boolean = False

    for ob in bpy.data.objects:
        if ob.name.startswith('@') or ob.halo_json.ObjectMesh_Type == 'COLLISION':
            boolean = True
    
    return boolean

def SceneHasPhysicsObject():
    boolean = False

    for ob in bpy.data.objects:
        if ob.name.startswith('$') or ob.halo_json.ObjectMesh_Type == 'PHYSICS':
            boolean = True
    
    return boolean

def SceneHasMarkers():
    boolean = False

    for ob in bpy.data.objects:
        if ob.name.startswith('#') or (ob.type == 'MESH' and ob.halo_json.Object_Type_All == 'MARKER') or (ob.halo_json.Object_Type_No_Mesh == 'MARKER' and ob.type == 'EMPTY'):
            boolean = True
    
    return boolean

def WriteStructureContents(metadata, asset_path, asset_name):
    print ('null')

def RenderPermExists():
    exists = False
    for ob in bpy.data.objects:
        halo_mesh = ob.halo_json
        halo_mesh_name = ob.name
        if (ob.type == 'MESH' and (not halo_mesh_name.startswith(special_prefixes)) and halo_mesh.Object_Type_All == 'MESH' and halo_mesh.ObjectMesh_Type == 'DEFAULT'):
            exists = True
    return exists

def PhysicsPermExists():
    exists = False
    for ob in bpy.data.objects:
        halo_mesh = ob.halo_json
        halo_mesh_name = ob.name
        if (ob.type == 'MESH' and (not halo_mesh_name.startswith(special_prefixes) or halo_mesh_name.startswith('$')) and (halo_mesh.ObjectMesh_Type == 'PHYSICS' or halo_mesh_name.startswith('$')) and halo_mesh.Object_Type_All == 'MESH'):
            exists = True
    return exists

def CollisionPermExists():
    exists = False
    for ob in bpy.data.objects:
        halo_mesh = ob.halo_json
        halo_mesh_name = ob.name
        if (ob.type == 'MESH' and (not halo_mesh_name.startswith(special_prefixes) or halo_mesh_name.startswith('@')) and (halo_mesh.ObjectMesh_Type == 'COLLISION' or halo_mesh_name.startswith('@')) and halo_mesh.Object_Type_All == 'MESH'):
            exists = True
    return exists

def save(operator, context, report,
        filepath="",
        export_sidecar=False,
        sidecar_type='MODEL',
        asset_path='',
        output_biped=False,
        output_crate=False,
        output_creature=False,
        output_device_control=False,
        output_device_machine=False,
        output_device_terminal=False,
        output_effect_scenery=False,
        output_equipment=False,
        output_giant=False,
        output_scenery=False,
        output_vehicle=False,
        output_weapon=False,
        **kwargs
        ):
    if export_sidecar and asset_path != '':
        export_xml(report, filepath, export_sidecar, sidecar_type, asset_path,output_biped,output_crate,output_creature,output_device_control,output_device_machine,output_device_terminal,output_effect_scenery,output_equipment,output_giant,output_scenery,output_vehicle,output_weapon)
    return {'FINISHED'}