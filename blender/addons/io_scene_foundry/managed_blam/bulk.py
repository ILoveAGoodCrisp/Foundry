

'''A collection of tools to read/write various tags in bulk'''

from pathlib import Path
from ..managed_blam.scenario_structure_bsp import ScenarioStructureBspTag
from ..managed_blam.animation import AnimationTag
from ..managed_blam.object import ObjectTag
from .. import utils

def report_state_names():
    '''Returns a list of all animation graphs and their state types (objects folder only)'''
    graphs = utils.paths_in_dir(str(Path(utils.get_tags_path(), 'objects')), '.model_animation_graph')
    state_names = set()
    for g in graphs:
        with AnimationTag(path=g) as animation:
            print('')
            print(animation.tag_path.RelativePath)
            print('-'*50)
            mode_block = animation.block_modes
            for element in mode_block.Elements:
                state_name = element.SelectField('label').GetStringData()
                print(f'--- {state_name}')
                state_names.add(state_name)

    print('\n\n\n')
    print(f'Found {len(graphs)} animation graphs')
    ordered_state_names = sorted(state_names)
    print(f'Found {len(ordered_state_names)} unique state names:')
    for name in ordered_state_names:
        print(f'--- {name}')
        
    return ordered_state_names

def report_seat_names():
    '''Returns a list of all seat names from vehicle and biped tags (objects folder only)'''
    vehicle_paths = utils.paths_in_dir(str(Path(utils.get_tags_path())) + 'objects', ('.vehicle', '.biped'))
    seat_names = set()
    for p in vehicle_paths:
        with ObjectTag(path=p) as vehicle:
            print('')
            print(vehicle.tag_path.RelativePath)
            print('-'*50)
            seats_block = vehicle.tag.SelectField('Struct:unit[0]/Block:seats')
            for element in seats_block.Elements:
                seat_name = element.SelectField('label').GetStringData()
                print(f'--- {seat_name}')
                seat_names.add(seat_name)

    print('\n\n\n')
    print(f'Found {len(vehicle_paths)} vehicle/biped tags')
    ordered_seat_names = sorted(seat_names)
    print(f'Found {len(ordered_seat_names)} unique seat names:')
    for name in ordered_seat_names:
        print(f'--- {name}')
        
    return ordered_seat_names

def report_blend_screens():
    '''Returns a list of blend screens'''
    graphs = utils.paths_in_dir(str(Path(utils.get_tags_path())) + 'objects', '.model_animation_graph')
    yaw_sources = set()
    pitch_sources = set()
    weight_sources = set()
    animation_names = set()
    for g in graphs:
        with AnimationTag(path=g) as animation:
            print('')
            print(animation.tag_path.RelativePath)
            print('-'*50)
            blend_screens_block = animation.tag.SelectField('Struct:definitions[0]/Block:NEW blend screens')
            functions_block = animation.tag.SelectField('Struct:definitions[0]/Block:functions')
            animations_block = animation.block_animations
            for element in blend_screens_block.Elements:
                print('====' + element.Fields[0].GetStringData() + '====')
                flags = element.Fields[1]
                print(f"--- active only when weapon down: {flags.TestBit('active only when weapon down')}")
                print(f"--- attempt piece-wise blending: {flags.TestBit('attempt piece-wise blending')}")
                print(f"--- allow parent adjustment: {flags.TestBit('allow parent adjustment')}")
                print(f"--- weight: {element.Fields[2].GetStringData()}")
                print(f"--- interpolation rate: {element.Fields[3].GetStringData()}")
                yaw_source = animation._Element_get_enum_as_string(element, 'yaw source')
                yaw_sources.add(yaw_source)
                print(f"--- yaw source: {yaw_source}")
                pitch_source = animation._Element_get_enum_as_string(element, 'pitch source')
                pitch_sources.add(pitch_source)
                print(f"--- pitch source: {pitch_source}")
                weight_source = animation._Element_get_enum_as_string(element, 'weight source')
                weight_sources.add(weight_source)
                print(f"--- weight source: {weight_source}")
                print(f"--- yaw source object function: {element.SelectField('yaw source object function').GetStringData()}")
                print(f"--- pitch source object function: {element.SelectField('pitch source object function').GetStringData()}")
                print(f"--- weight source object function: {element.SelectField('weight source object function').GetStringData()}")
                weight_function_index = element.SelectField('weight function').Value
                if weight_function_index > -1:
                    print(f"--- weight function: {functions_block.Elements[weight_function_index].Fields[0].GetStringData()}")
                    'Struct:definitions[0]/Block:NEW blend screens[135]/Struct:animation[0]/ShortBlockIndex:animation'
                animation_index = element.SelectField('Struct:animation[0]/ShortBlockIndex:animation').Value
                if animation_index > -1:
                    animation_name = animations_block.Elements[animation_index].Fields[0].GetStringData()
                    animation_names.add(utils.any_partition(animation_name, ':', True))
                    print(f"--- animation: {animation_name}")
                            
    print('\n\n\n')
    ordered_yaw_sources = sorted(yaw_sources)
    print(f'Found {len(yaw_sources)} unique yaw sources:')
    for name in ordered_yaw_sources:
        print(f'--- {name}')
    print('\n')
    ordered_pitch_sources = sorted(pitch_sources)
    print(f'Found {len(pitch_sources)} unique pitch sources:')
    for name in ordered_pitch_sources:
        print(f'--- {name}')
    print('\n')
    ordered_weight_sources = sorted(weight_sources)
    print(f'Found {len(weight_sources)} unique weight sources:')
    for name in ordered_weight_sources:
        print(f'--- {name}')
    print('\n')
    ordered_animations = sorted(animation_names)
    print(f'Found {len(animation_names)} unique animation state names:')
    for name in ordered_animations:
        print(f'--- {name}')
        
def report_prefab_lightmap_res():
    bsps = utils.paths_in_dir(Path(utils.get_tags_path()), '.scenario_structure_bsp')
    lm_res_list = []
    for b in bsps:
        with ScenarioStructureBspTag(path=b) as tag:
                for element in tag.block_prefabs.Elements:
                    lm_res = int(element.SelectField("override lightmap resolution scale").GetStringData())
                    if lm_res > 0 and lm_res != 3:
                        lm_res_list.append([tag.tag_path.RelativePath, element.ElementIndex, lm_res])
                        
    print(f'Found {len(lm_res_list)} set lightmap res overrides:')
    print('\n')
    for items in lm_res_list:
        print(items[2], items[1], items[0])
        
def report_instance_lightmap_res():
    bsps = utils.paths_in_dir(Path(utils.get_tags_path()), '.scenario_structure_bsp')
    lm_res_list = []
    for b in bsps:
        with ScenarioStructureBspTag(path=b) as tag:
                for element in tag.block_instances.Elements:
                    lm_res = float(element.SelectField("lightmap resolution scale").GetStringData())
                    if lm_res != 1:
                        lm_res_list.append([tag.tag_path.RelativePath, element.ElementIndex, lm_res])
                        
    print(f'Found {len(lm_res_list)} set lightmap resses:')
    print('\n')
    for items in lm_res_list:
        print(items[2], items[1], items[0])