"""Rebuild planar collision outlines without losing shared boundary vertices."""
from collections import Counter,defaultdict
import math
import bmesh

def _projection(vertices):
    points=[tuple(v.co) for v in vertices]
    n=[0.,0.,0.]
    for a,b in zip(points,points[1:]+points[:1]):
        n[0]+=(a[1]-b[1])*(a[2]+b[2])
        n[1]+=(a[2]-b[2])*(a[0]+b[0])
        n[2]+=(a[0]-b[0])*(a[1]+b[1])
    axis=max(range(3),key=lambda i:abs(n[i]))
    axes=[i for i in range(3) if i!=axis]
    return [(p[axes[0]],p[axes[1]]) for p in points]

def _stable_triangles(vertices):
    """Maximize the smallest triangle altitude within the original outline."""
    n=len(vertices)
    if n>80:return None
    p=_projection(vertices)
    def cross(a,b,c):return (b[0]-a[0])*(c[1]-a[1])-(b[1]-a[1])*(c[0]-a[0])
    signed=sum(a[0]*b[1]-a[1]*b[0] for a,b in zip(p,p[1:]+p[:1]))
    sign=1 if signed>0 else -1
    def inside(point):
        count=False
        for a,b in zip(p,p[1:]+p[:1]):
            if (a[1]>point[1])!=(b[1]>point[1]) and point[0]<(b[0]-a[0])*(point[1]-a[1])/(b[1]-a[1])+a[0]:count=not count
        return count
    def diagonal(i,j):
        if abs(i-j)==1 or {i,j}=={0,n-1}:return True
        a,b=p[i],p[j]
        for k in range(n):
            l=(k+1)%n
            if i in (k,l) or j in (k,l):continue
            c,d=p[k],p[l]
            if cross(a,b,c)*cross(a,b,d)<0 and cross(c,d,a)*cross(c,d,b)<0:return False
        return inside(((a[0]+b[0])/2,(a[1]+b[1])/2))
    legal={(i,j):diagonal(i,j) for i in range(n) for j in range(i+1,n)}
    scores={(i,i+1):math.inf for i in range(n-1)}
    splits={}
    for length in range(2,n):
        for i in range(n-length):
            j=i+length
            if not legal[i,j]:continue
            best=-1
            for k in range(i+1,j):
                if (i,k) not in scores or (k,j) not in scores:continue
                area=sign*cross(p[i],p[k],p[j])
                if area<=0:continue
                longest=max(math.dist(p[i],p[k]),math.dist(p[k],p[j]),math.dist(p[j],p[i]))
                score=min(scores[i,k],scores[k,j],area/longest)
                if score>best:best=score;splits[i,j]=k
            if best>=0:scores[i,j]=best
    if (0,n-1) not in scores:return None
    def triangles(i,j):
        if j==i+1:return []
        k=splits[i,j]
        return triangles(i,k)+[(vertices[i],vertices[k],vertices[j])]+triangles(k,j)
    return triangles(0,n-1)

def reconstruct_collision_outline(mesh):
    if not mesh.attributes.get('.foundry_collision_plane') or mesh.has_custom_normals:return 0,0
    bm=bmesh.new();cleaned=triangulated=0
    try:
        bm.from_mesh(mesh)
        bm.verts.index_update()
        plane=bm.faces.layers.int.get(".foundry_collision_plane")
        for face in list(bm.faces):
            if len(face.verts)<4 or face[plane]<0:continue
            vertices=list(face.verts)
            epsilon=max(abs(c) for v in vertices for c in v.co)*2**-22
            edges=Counter()
            for a,b in zip(vertices,vertices[1:]+vertices[:1]):
                delta=b.co-a.co
                if not delta.length_squared:continue
                splits=[(0,a),(1,b)]
                for v in vertices:
                    if v in (a,b):continue
                    t=(v.co-a.co).dot(delta)/delta.length_squared
                    if 0<t<1 and (v.co-(a.co+t*delta)).length<=epsilon:splits.append((t,v))
                splits.sort(key=lambda q:q[0])
                for (_,v),(_,w) in zip(splits,splits[1:]):
                    if edges[w,v]:edges[w,v]-=1
                    else:edges[v,w]+=1
            original={(a,b) for a,b in zip(vertices,vertices[1:]+vertices[:1])}
            remaining={edge for edge,count in edges.items() if count}
            if remaining!=original and len(remaining)<len(original):
                outgoing=defaultdict(list)
                for a,b in remaining:outgoing[a].append(b)
                if outgoing and all(len(nexts)==1 for nexts in outgoing.values()):
                    first=min(outgoing,key=lambda v:v.index)
                    ring=[first];current=outgoing[first][0]
                    while current!=first and current not in ring and current in outgoing:
                        ring.append(current);current=outgoing[current][0]
                    if current==first and len(ring)>=3 and len(ring)==len(remaining):
                        new=bm.faces.new(ring,face)
                        bm.faces.remove(face);face=new;vertices=ring;cleaned+=1
            triangles=_stable_triangles(vertices)
            if triangles is None:continue
            # Change only problematic outlines. Ordinary source triangulation
            # remains with Blender to avoid perturbing the compiler globally.
            test=bmesh.new()
            tv=[test.verts.new(v.co) for v in vertices]
            tf=test.faces.new(tv)
            bmesh.ops.triangulate(test,faces=[tf],quad_method='BEAUTY',ngon_method='BEAUTY')
            altitude=lambda v:((v[1].co-v[0].co).cross(v[2].co-v[0].co)).length/max((v[a].co-v[b].co).length for a,b in ((0,1),(1,2),(2,0)))
            worst=min(altitude(list(f.verts)) for f in test.faces)
            test.free()
            quality=min(altitude(list(t)) for t in triangles)
            if worst<epsilon*4 and quality>max(epsilon*8,worst*4):
                for tri in triangles:bm.faces.new(tri,face)
                bm.faces.remove(face);triangulated+=1
        if not (cleaned or triangulated):
            return 0,0
        # Reconnect only newly exposed junctions using the same rounding bound.
        for edge in list(bm.edges):
            if not edge.is_valid or not edge.is_boundary:continue
            a,b=edge.verts;delta=b.co-a.co
            if not delta.length_squared:continue
            epsilon=max(abs(c) for v in (a,b) for c in v.co)*2**-22
            candidates=[]
            for v in bm.verts:
                if v in (a,b) or not v.is_boundary or any(v in f.verts for f in edge.link_faces):continue
                t=(v.co-a.co).dot(delta)/delta.length_squared
                if 0<t<1 and (v.co-(a.co+t*delta)).length<=epsilon:candidates.append((t,v))
            current=edge;start=a;previous=0
            for t,v in sorted(candidates,key=lambda p:p[0]):
                if not current.is_valid:break
                next_edge,new=bmesh.utils.edge_split(current,start,(t-previous)/(1-previous))
                new.co=v.co
                start=new;current=bm.edges.get((new,b));previous=t
        if cleaned or triangulated:
            from .classic_geometry import weld_classic_vertices
            from .. import utils
            bm.to_mesh(mesh);mesh.update()
            weld_classic_vertices(mesh)
            utils.calc_face_prop_counts(mesh)
    finally:bm.free()
    return cleaned,triangulated
