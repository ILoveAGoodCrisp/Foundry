import bpy, json
from pathlib import Path
root=Path(r'G:\Halo\Modding\Foundry')
with bpy.data.libraries.load(str(root/'blender/addons/io_scene_foundry/blends/h1_nodes.blend'),link=False) as (s,d): d.node_groups=[n for n in s.node_groups if n.startswith('foundry_h1.')]
for g in d.node_groups:
 print('\nGROUP',g.name)
 for n in g.nodes:
  print('NODE',n.name,n.type,getattr(n,'operation',''),getattr(n,'blend_type',''),getattr(n,'node_tree',None))
  if n.type not in {'GROUP_INPUT','GROUP_OUTPUT'}:
   print('VALUES',[(s.name,str(s.default_value)) for s in n.inputs if not s.is_linked and hasattr(s,'default_value')])
 for l in g.links: print('LINK',l.from_node.name,l.from_socket.name,'->',l.to_node.name,l.to_socket.name)
