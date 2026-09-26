import bpy, json
from pathlib import Path
root=Path(r'G:\Halo\Modding\Foundry')
result={}
for lib,prefix in [('h1_nodes','foundry_h1.'),('h3_nodes','foundry_h3.'),('reach_nodes','foundry_reach.'),('h4_nodes','')]:
 with bpy.data.libraries.load(str(root/'blender/addons/io_scene_foundry/blends'/f'{lib}.blend'),link=False) as (src,dst):
  dst.node_groups=[n for n in src.node_groups if n.startswith(prefix)]
 result[lib]={}
 for group in dst.node_groups:
  mat=bpy.data.materials.new('inspect'); mat.use_nodes=True
  node=mat.node_tree.nodes.new('ShaderNodeGroup'); node.node_tree=group
  sockets=[]
  for s in node.inputs:
   v=getattr(s,'default_value',None)
   if v is not None and not isinstance(v,(str,int,float,bool)): v=list(v)
   sockets.append([s.name,s.type,v])
  result[lib][group.name]=sockets
  bpy.data.materials.remove(mat)
(root/'.tmp-material-mapping/interfaces.json').write_text(json.dumps(result,indent=2))
print({k:list(v) for k,v in result.items()})
