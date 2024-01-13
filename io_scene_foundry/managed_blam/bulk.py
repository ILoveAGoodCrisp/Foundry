# ##### BEGIN MIT LICENSE BLOCK #####
#
# MIT License
#
# Copyright (c) 2024 Crisp
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

'''A collection of tools to read/write various tags in bulk'''

from io_scene_foundry.managed_blam.animation import AnimationTag
from io_scene_foundry.managed_blam.object import ObjectTag
from io_scene_foundry.utils import nwo_utils

def report_state_names():
    '''Returns a list of all animation graphs and their state types (objects folder only)'''
    graphs = nwo_utils.paths_in_dir(nwo_utils.get_tags_path() + 'objects', '.model_animation_graph')
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
    vehicle_paths = nwo_utils.paths_in_dir(nwo_utils.get_tags_path() + 'objects', ('.vehicle', '.biped'))
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
    