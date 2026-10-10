use crate::binary::{Address, Builder, Storage};
use crate::input::{Graph, Result, Value};
use crate::math::{self, Context};
use crate::schema::Registry;
use crate::validate::{buffer, vertices_count};
use std::collections::{HashMap, HashSet};

#[derive(Clone, Copy)]
pub struct Options {
    pub sections: usize,
    pub types: usize,
    pub objects: usize,
    pub strings: usize,
    pub buffers: usize,
}
pub struct Writer<'a> {
    pub g: &'a Graph,
    pub b: Builder,
    pub r: Registry,
    pub c: Context,
    pub o: Options,
    defs: HashMap<usize, Address>,
    owners: HashMap<(usize, String), (Address, usize, usize)>,
    written: HashSet<Address>,
    pub vector_keys: HashMap<usize, u32>,
}
impl<'a> Writer<'a> {
    pub fn new(g: &'a Graph, o: Options) -> Result<Self> {
        if [o.types, o.objects, o.strings, o.buffers]
            .iter()
            .any(|s| *s >= o.sections)
        {
            return Err("Invalid section placement".into());
        }
        crate::validate::validate(g)?;
        Ok(Self {
            g,
            b: Builder::new(o.sections)?,
            r: Registry::new()?,
            c: Context::new(g)?,
            o,
            defs: HashMap::new(),
            owners: HashMap::new(),
            written: HashSet::new(),
            vector_keys: HashMap::new(),
        })
    }
    pub fn ty(&mut self, id: usize) -> Result<Address> {
        if let Some(a) = self.defs.get(&id) {
            return Ok(*a);
        }
        let members = self.r.schemas[id].members.clone();
        let a = self
            .b
            .alloc((members.len() + 1) * 44, self.o.types, 4, Storage::Word)?;
        self.defs.insert(id, a);
        for (i, m) in members.iter().enumerate() {
            let row = a.at(i * 44);
            self.b.u32(row, m.kind as usize)?;
            self.string(row.at(4), &m.name)?;
            if let Some(name) = &m.reference {
                let child = self.r.named(name)?;
                let destination = self.ty(child)?;
                self.b.reference(row.at(12), Some(destination))?;
            }
            self.b.u32(row.at(20), m.width)?;
            for j in 0..3 {
                self.b.i32(row.at(24 + j * 4), m.extra[j] as i64)?;
            }
        }
        Ok(a)
    }
    pub fn reserve(
        &mut self,
        id: usize,
        role: &str,
        schema: usize,
        count: usize,
        section: usize,
    ) -> Result<Option<Address>> {
        if count == 0 {
            return Ok(None);
        }
        let key = (id, role.to_owned());
        if let Some((a, s, n)) = self.owners.get(&key) {
            if *s != schema || *n != count || self.b.blocks[a.block].section != section {
                return Err("Shared allocation has inconsistent shape".into());
            }
            return Ok(Some(*a));
        }
        let layout = self.r.layout(schema)?;
        if layout.size == 0 {
            return Err("Nonempty typed data has zero size".into());
        }
        let alignment = match layout.storage {
            Storage::Byte => 1,
            Storage::Half => 2,
            _ => 4,
        };
        let size = layout
            .size
            .checked_mul(count)
            .ok_or("Typed allocation size overflow")?;
        let a = self.b.alloc(size, section, alignment, layout.storage)?;
        self.owners.insert(key, (a, schema, count));
        if layout.storage == Storage::Mixed {
            let t = self.ty(schema)?;
            self.b.mixed(a, count, t, layout.size)?;
        }
        Ok(Some(a))
    }
    pub fn body(&mut self, id: usize, schema: &str) -> Result<Address> {
        let s = self.r.named(schema)?;
        Ok(self.reserve(id, "body", s, 1, self.o.objects)?.unwrap())
    }
    pub fn field(&mut self, a: Address, schema: &str, field: &str) -> Result<Address> {
        let s = self.r.named(schema)?;
        Ok(a.at(self.r.offset(s, field)?))
    }
    pub fn string(&mut self, a: Address, text: &str) -> Result<()> {
        let destination = self.b.string(text, self.o.strings)?;
        self.b.reference(a, Some(destination))
    }
    pub fn transform(&mut self, a: Address, value: &Value) -> Result<()> {
        let m = math::matrix(value)?;
        let (flags, parts) = math::packed(self.c.similarity(m))?;
        self.b.u32(a, flags as usize)?;
        for (i, v) in parts.into_iter().enumerate() {
            self.b.f32(a.at(4 + i * 4), v)?;
        }
        Ok(())
    }
    pub fn variant(&mut self, a: Address, id: usize) -> Result<()> {
        let schema = self.r.metadata(self.g, id)?;
        let object = self.metadata(id)?;
        let ty = if self.g.list(id, "members")?.is_empty() {
            None
        } else {
            Some(self.ty(schema)?)
        };
        self.b.reference(a, ty)?;
        self.b.reference(a.at(8), object)
    }
    pub fn metadata(&mut self, id: usize) -> Result<Option<Address>> {
        let schema = self.r.metadata(self.g, id)?;
        if self.g.list(id, "members")?.is_empty() {
            return Ok(None);
        }
        let a = self
            .reserve(id, "metadata", schema, 1, self.o.objects)?
            .unwrap();
        if self.written.insert(a) {
            self.metadata_inline(a, id, schema)?;
        }
        Ok(Some(a))
    }
    pub fn metadata_inline(&mut self, a: Address, id: usize, schema: usize) -> Result<()> {
        let g = self.g;
        let layout = self.r.layout(schema)?;
        for (index, m) in g.ids(id, "members")?.into_iter().enumerate() {
            let p = a.at(layout.offsets[index]);
            let value = g.field(m, "value")?;
            match g.text(m, "kind")? {
                "int32" => self.b.i32(p, value.int()?)?,
                "real32" => self.b.f32(p, value.real()?)?,
                "string" => self.string(p, value.text()?)?,
                "int32_array" | "real32_array" => {
                    for (j, v) in value.list()?.iter().enumerate() {
                        if g.text(m, "kind")? == "int32_array" {
                            self.b.i32(p.at(j * 4), v.int()?)?;
                        } else {
                            self.b.f32(p.at(j * 4), v.real()?)?;
                        }
                    }
                }
                "reference" => {
                    let destination = self.metadata(value.reference()?)?;
                    self.b.reference(p, destination)?;
                }
                "record_array" | "variant_array" => {
                    let values = value.list()?;
                    let variants = g.text(m, "kind")? == "variant_array";
                    let element = if variants {
                        Some(self.r.named("Variant")?)
                    } else if let Some(first) = values.first() {
                        Some(self.r.metadata(g, first.reference()?)?)
                    } else {
                        None
                    };
                    let ty = if let Some(s) = element {
                        Some(self.ty(s)?)
                    } else {
                        None
                    };
                    self.b.reference(p, ty)?;
                    self.b.i32(p.at(8), values.len() as i64)?;
                    let mut array = None;
                    if let Some(s) = element {
                        let stride = self.r.layout(s)?.size;
                        if !values.is_empty() {
                            let start = if stride == 0 {
                                self.b.alloc(1, self.o.objects, 1, Storage::Byte)?
                            } else {
                                self.reserve(m, "metadata_array", s, values.len(), self.o.objects)?
                                    .unwrap()
                            };
                            array = Some(start);
                            if self.written.insert(start) && stride > 0 {
                                for (j, v) in values.iter().enumerate() {
                                    if variants {
                                        self.variant(start.at(j * stride), v.reference()?)?;
                                    } else {
                                        self.metadata_inline(
                                            start.at(j * stride),
                                            v.reference()?,
                                            s,
                                        )?;
                                    }
                                }
                            }
                        }
                    }
                    self.b.reference(p.at(12), array)?;
                }
                _ => return Err("Unsupported metadata kind".into()),
            }
        }
        Ok(())
    }
    // Describes a field in its parent and the separately owned typed payload.
    #[allow(clippy::too_many_arguments)]
    fn array(
        &mut self,
        parent: Address,
        schema: &str,
        field: &str,
        element: &str,
        id: usize,
        role: &str,
        count: usize,
    ) -> Result<Option<Address>> {
        let p = self.field(parent, schema, field)?;
        self.b.i32(p, count as i64)?;
        let s = self.r.named(element)?;
        let a = self.reserve(id, role, s, count, self.o.objects)?;
        self.b.reference(p.at(4), a)?;
        Ok(a)
    }
    pub fn vertices(&mut self, id: usize) -> Result<Address> {
        let g = self.g;
        let header = self.body(id, "VertexData")?;
        if !self.written.insert(header) {
            return Ok(header);
        }
        let count = vertices_count(g, id)?;
        let schema = self.r.vertex(g, id)?;
        let stride = self.r.layout(schema)?.size;
        let p = self.field(header, "VertexData", "Vertices")?;
        let dtype = self.ty(schema)?;
        self.b.reference(p, Some(dtype))?;
        self.b.i32(p.at(8), count as i64)?;
        let payload = self.reserve(id, "interleaved", schema, count, self.o.buffers)?;
        if let Some(array) = payload {
            let placement = math::matrix(g.field(id, "placement")?)?;
            let reflected = g.boolean(id, "reflect_y")?;
            let deltas = g.boolean(id, "data_is_deltas")?;
            let mut offset = 0;
            let mut output = vec![0u8; stride.checked_mul(count).ok_or("Vertex size overflow")?];
            for attribute in g.ids(id, "attributes")? {
                let b = buffer(g, g.id(attribute, "buffer")?)?;
                let name = g.text(attribute, "name")?;
                let unit = b.width * b.unit();
                let spatial = matches!(name, "Position" | "Normal" | "Tangent" | "Binormal");
                if spatial {
                    let stages = self
                        .c
                        .stages(placement, reflected, name == "Normal", deltas)?;
                    for row in 0..count {
                        let v = self.c.spatial(
                            [b.real(row * 3), b.real(row * 3 + 1), b.real(row * 3 + 2)],
                            &stages,
                            name == "Position",
                            deltas,
                        )?;
                        for (k, x) in v.into_iter().enumerate() {
                            let start = row * stride + offset + k * 4;
                            output[start..start + 4].copy_from_slice(&(x as f32).to_le_bytes());
                        }
                    }
                } else {
                    for row in 0..count {
                        output[row * stride + offset..row * stride + offset + unit]
                            .copy_from_slice(&b.bytes[row * unit..row * unit + unit]);
                    }
                }
                offset += unit;
            }
            self.b.write(array, &output)?;
        }
        self.b.reference(p.at(12), payload)?;
        let attrs = g.ids(id, "attributes")?;
        if let Some(a) = self.array(
            header,
            "VertexData",
            "VertexComponentNames",
            "String",
            id,
            "components",
            attrs.len(),
        )? {
            for (j, attribute) in attrs.into_iter().enumerate() {
                self.string(a.at(j * 8), g.text(attribute, "component_name")?)?;
            }
        }
        Ok(header)
    }
    pub fn topology(&mut self, id: usize) -> Result<Address> {
        let g = self.g;
        let header = self.body(id, "TriTopology")?;
        if !self.written.insert(header) {
            return Ok(header);
        }
        let groups = g.ids(id, "groups")?;
        if let Some(a) = self.array(
            header,
            "TriTopology",
            "Groups",
            "TriMaterialGroup",
            id,
            "groups",
            groups.len(),
        )? {
            for (j, group) in groups.into_iter().enumerate() {
                for (k, field) in ["material_index", "first_triangle", "triangle_count"]
                    .into_iter()
                    .enumerate()
                {
                    self.b.i32(a.at(j * 12 + k * 4), g.int(group, field)?)?;
                }
            }
        }
        let indices = g.id(id, "indices")?;
        let b = buffer(g, indices)?;
        let short = b.scalar == "uint16";
        let field = if short { "Indices16" } else { "Indices" };
        let element = if short { "Int16" } else { "Int32" };
        let p = self.field(header, "TriTopology", field)?;
        self.b.i32(p, b.count as i64)?;
        let s = self.r.named(element)?;
        let payload = self.reserve(id, "indices", s, b.count, self.o.buffers)?;
        if let Some(a) = payload {
            let mut bytes = Vec::with_capacity(b.bytes.len());
            for triangle in 0..b.count / 3 {
                let mut values = [
                    b.index(triangle * 3),
                    b.index(triangle * 3 + 1),
                    b.index(triangle * 3 + 2),
                ];
                if g.boolean(id, "invert_winding")? {
                    values.reverse();
                }
                if g.boolean(id, "reflect_winding")? {
                    values.swap(1, 2);
                }
                if self.c.reorder {
                    values.reverse();
                }
                for value in values {
                    if short {
                        bytes.extend_from_slice(&(value as u16).to_le_bytes());
                    } else {
                        bytes.extend_from_slice(&(value as i32).to_le_bytes());
                    }
                }
            }
            self.b.write(a, &bytes)?;
        }
        self.b.reference(p.at(4), payload)?;
        let annotations = g.ids(id, "annotations")?;
        if let Some(a) = self.array(
            header,
            "TriTopology",
            "TriAnnotationSets",
            "TriAnnotationSet",
            id,
            "annotations",
            annotations.len(),
        )? {
            let sid = self.r.named("TriAnnotationSet")?;
            let stride = self.r.layout(sid)?.size;
            for (j, annotation) in annotations.into_iter().enumerate() {
                let row = a.at(j * stride);
                let f = self.field(row, "TriAnnotationSet", "Name")?;
                self.string(f, g.text(annotation, "name")?)?;
                let schema = self.r.annotation(g, annotation)?;
                let b = buffer(g, g.id(annotation, "buffer")?)?;
                let p = self.field(row, "TriAnnotationSet", "TriAnnotations")?;
                let ty = self.ty(schema)?;
                self.b.reference(p, Some(ty))?;
                self.b.i32(p.at(8), b.count as i64)?;
                let values = self.reserve(annotation, "values", schema, b.count, self.o.buffers)?;
                if let Some(v) = values {
                    self.b.write(v, b.bytes)?;
                }
                self.b.reference(p.at(12), values)?;
                let p = self.field(row, "TriAnnotationSet", "IndicesMapFromTriToAnnotation")?;
                self.b
                    .i32(p, i64::from(g.boolean(annotation, "map_from_tri")?))?;
                if let Some(remap) = g.opt(annotation, "indices")? {
                    let rb = buffer(g, remap)?;
                    let p = self.field(row, "TriAnnotationSet", "TriAnnotationIndices")?;
                    self.b.i32(p, rb.count as i64)?;
                    let s = self.r.named("Int32")?;
                    let data = self.reserve(remap, "remap", s, rb.count, self.o.buffers)?;
                    if let Some(d) = data {
                        self.b.write(d, rb.bytes)?;
                    }
                    self.b.reference(p.at(4), data)?;
                }
            }
        }
        Ok(header)
    }
    pub fn mesh(&mut self, id: usize) -> Result<Address> {
        let g = self.g;
        let header = self.body(id, "Mesh")?;
        if !self.written.insert(header) {
            return Ok(header);
        }
        let p = self.field(header, "Mesh", "Name")?;
        self.string(p, g.text(id, "name")?)?;
        let v = self.vertices(g.id(id, "vertices")?)?;
        let p = self.field(header, "Mesh", "PrimaryVertexData")?;
        self.b.reference(p, Some(v))?;
        let t = self.topology(g.id(id, "topology")?)?;
        let p = self.field(header, "Mesh", "PrimaryTopology")?;
        self.b.reference(p, Some(t))?;
        let p = self.field(header, "Mesh", "ExtendedData")?;
        self.variant(p, g.id(id, "metadata")?)?;
        let morphs = g.ids(id, "morph_targets")?;
        if let Some(a) = self.array(
            header,
            "Mesh",
            "MorphTargets",
            "MorphTarget",
            id,
            "morphs",
            morphs.len(),
        )? {
            for (j, morph) in morphs.into_iter().enumerate() {
                let row = a.at(j * 20);
                if !matches!(g.field(morph, "name")?, Value::Null) {
                    self.string(row, g.text(morph, "name")?)?;
                }
                let vid = g.id(morph, "vertex_data")?;
                let v = self.vertices(vid)?;
                self.b.reference(row.at(8), Some(v))?;
                self.b
                    .i32(row.at(16), i64::from(g.boolean(vid, "data_is_deltas")?))?;
            }
        }
        let materials = g.ids(id, "materials")?;
        if let Some(a) = self.array(
            header,
            "Mesh",
            "MaterialBindings",
            "MaterialBinding",
            id,
            "materials",
            materials.len(),
        )? {
            for (j, m) in materials.into_iter().enumerate() {
                let destination = self.material(m)?;
                self.b.reference(a.at(j * 8), Some(destination))?;
            }
        }
        let bones = g.list(id, "bone_bindings")?;
        if let Some(a) = self.array(
            header,
            "Mesh",
            "BoneBindings",
            "BoneBinding",
            id,
            "bindings",
            bones.len(),
        )? {
            let (low, high) = self.c.bounds()?;
            for (j, name) in bones.iter().enumerate() {
                let row = a.at(j * 44);
                self.string(row, name.text()?)?;
                for k in 0..3 {
                    self.b.f32(row.at(8 + k * 4), low[k])?;
                    self.b.f32(row.at(20 + k * 4), high[k])?;
                }
            }
        }
        Ok(header)
    }
    pub fn material(&mut self, id: usize) -> Result<Address> {
        let g = self.g;
        let header = self.body(id, "Material")?;
        if !self.written.insert(header) {
            return Ok(header);
        }
        let p = self.field(header, "Material", "Name")?;
        self.string(p, g.text(id, "name")?)?;
        let p = self.field(header, "Material", "ExtendedData")?;
        self.variant(p, g.id(id, "metadata")?)?;
        let texture = if let Some(t) = g.opt(id, "texture")? {
            Some(self.texture(t)?)
        } else {
            None
        };
        let p = self.field(header, "Material", "Texture")?;
        self.b.reference(p, texture)?;
        let maps = g.ids(id, "maps")?;
        if let Some(a) = self.array(
            header,
            "Material",
            "Maps",
            "MaterialMap",
            id,
            "maps",
            maps.len(),
        )? {
            for (j, map) in maps.into_iter().enumerate() {
                let row = a.at(j * 16);
                self.string(row, g.text(map, "usage")?)?;
                let dest = self.material(g.id(map, "material")?)?;
                self.b.reference(row.at(8), Some(dest))?;
            }
        }
        Ok(header)
    }
    pub fn texture(&mut self, id: usize) -> Result<Address> {
        let g = self.g;
        let header = self.body(id, "Texture")?;
        if !self.written.insert(header) {
            return Ok(header);
        }
        let p = self.field(header, "Texture", "FromFileName")?;
        self.string(p, g.text(id, "name")?)?;
        let images = g.ids(id, "images")?;
        let first = images[0];
        let p = self.field(header, "Texture", "TextureType")?;
        for (i, v) in [0, g.int(first, "width")?, g.int(first, "height")?, 1, 0]
            .into_iter()
            .enumerate()
        {
            self.b.i32(p.at(i * 4), v)?;
        }
        let p = self.field(header, "Texture", "Layout")?;
        for (i, v) in [4, 0, 8, 16, 24, 8, 8, 8, 8].into_iter().enumerate() {
            self.b.i32(p.at(i * 4), v)?;
        }
        if let Some(a) = self.array(
            header,
            "Texture",
            "Images",
            "TextureImage",
            id,
            "images",
            images.len(),
        )? {
            for (j, image) in images.into_iter().enumerate() {
                let row = a.at(j * 12);
                self.b.i32(row, 1)?;
                let s = self.r.named("TextureMIPLevel")?;
                let mip = self.reserve(image, "mip", s, 1, self.o.objects)?.unwrap();
                self.b.reference(row.at(4), Some(mip))?;
                if self.written.insert(mip) {
                    let pixels = g.bytes(image, "rgba")?;
                    self.b.i32(mip, g.int(image, "stride")?)?;
                    self.b.i32(mip.at(4), pixels.len() as i64)?;
                    let s = self.r.named("UInt8")?;
                    let data = self
                        .reserve(image, "pixels", s, pixels.len(), self.o.buffers)?
                        .unwrap();
                    self.b.write(data, pixels)?;
                    self.b.reference(mip.at(8), Some(data))?;
                }
            }
        }
        Ok(header)
    }
    pub fn skeleton(&mut self, id: usize) -> Result<Address> {
        let g = self.g;
        let header = self.body(id, "Skeleton")?;
        if !self.written.insert(header) {
            return Ok(header);
        }
        let p = self.field(header, "Skeleton", "Name")?;
        self.string(p, g.text(id, "name")?)?;
        let p = self.field(header, "Skeleton", "LODType")?;
        self.b.i32(p, g.int(id, "lod_type")?)?;
        let p = self.field(header, "Skeleton", "ExtendedData")?;
        self.variant(p, g.id(id, "metadata")?)?;
        let bones = g.ids(id, "bones")?;
        if let Some(a) = self.array(
            header,
            "Skeleton",
            "Bones",
            "Bone",
            id,
            "bones",
            bones.len(),
        )? {
            for (j, bone) in bones.into_iter().enumerate() {
                let row = a.at(j * 164);
                self.string(row, g.text(bone, "name")?)?;
                self.b.i32(row.at(8), g.int(bone, "parent_index")?)?;
                self.transform(row.at(12), g.field(bone, "local_matrix")?)?;
                let inverse = self
                    .c
                    .inverse_world(math::matrix(g.field(bone, "world_matrix")?)?)?;
                for (k, v) in inverse.into_iter().enumerate() {
                    self.b.f32(row.at(80 + k * 4), v)?;
                }
                self.b.f32(row.at(144), g.real(bone, "lod_error")?)?;
                self.variant(row.at(148), g.id(bone, "metadata")?)?;
            }
        }
        Ok(header)
    }
    pub fn model(&mut self, id: usize) -> Result<Address> {
        let g = self.g;
        let header = self.body(id, "Model")?;
        if !self.written.insert(header) {
            return Ok(header);
        }
        self.string(header, g.text(id, "name")?)?;
        let skeleton = self.skeleton(g.id(id, "skeleton")?)?;
        self.b.reference(header.at(8), Some(skeleton))?;
        self.transform(header.at(16), g.field(id, "placement")?)?;
        self.variant(header.at(96), g.id(id, "metadata")?)?;
        let meshes = g.list(id, "meshes")?;
        if let Some(a) = self.array(
            header,
            "Model",
            "MeshBindings",
            "ModelMeshBinding",
            id,
            "meshes",
            meshes.len(),
        )? {
            for (j, item) in meshes.iter().enumerate() {
                let mesh = if let Some(m) = item.optional_ref()? {
                    Some(self.mesh(m)?)
                } else {
                    None
                };
                self.b.reference(a.at(j * 8), mesh)?;
            }
        }
        Ok(header)
    }
    fn curve(&mut self, a: Address, id: usize, role: &str) -> Result<()> {
        let g = self.g;
        let schema = self.r.named("CurveDataDaKeyframes32f")?;
        let header = self.reserve(id, role, schema, 1, self.o.objects)?.unwrap();
        let ty = self.ty(schema)?;
        self.b.reference(a, Some(ty))?;
        self.b.reference(a.at(8), Some(header))?;
        if !self.written.insert(header) {
            return Ok(());
        }
        let controls = g.id(id, "controls")?;
        let source = buffer(g, controls)?;
        if source.scalar != "real32" || source.count == 0 {
            return Err("Curves require nonempty float32 controls".into());
        }
        self.b.write(header, &[0, 0])?;
        self.b
            .write(header.at(2), &(source.width as i16).to_le_bytes())?;
        self.b
            .i32(header.at(4), (source.count * source.width) as i64)?;
        let s = self.r.named("Real32")?;
        let data = self
            .reserve(
                id,
                &format!("{role}.controls"),
                s,
                source.count * source.width,
                self.o.buffers,
            )?
            .unwrap();
        if role == "vector" {
            self.b.write(data, source.bytes)?;
        } else {
            let mut output = Vec::with_capacity(source.bytes.len());
            for row in 0..source.count {
                let mut values = (0..source.width)
                    .map(|i| source.real(row * source.width + i))
                    .collect::<Vec<_>>();
                match role {
                    "position" => {
                        let mut value = [values[0], values[1], values[2]];
                        if self.c.reflected {
                            value = math::vector(math::MIRROR, value);
                        }
                        value = math::vector(self.c.linear, value);
                        for i in 0..3 {
                            values[i] = value[i] + self.c.translation[i];
                        }
                    }
                    "orientation" => {
                        let mut xyz = [values[0], values[1], values[2]];
                        if self.c.reflected {
                            xyz = [-xyz[0], xyz[1], -xyz[2]];
                        }
                        xyz = math::vector(self.c.rotation, xyz);
                        for i in 0..3 {
                            values[i] = self.c.handedness * xyz[i];
                        }
                    }
                    "scale_shear" => {
                        let mut shear =
                            std::array::from_fn(|i| std::array::from_fn(|j| values[i * 3 + j]));
                        if self.c.reflected {
                            shear =
                                math::multiply(math::multiply(math::MIRROR, shear), math::MIRROR);
                        }
                        shear =
                            math::multiply(math::multiply(self.c.linear, shear), self.c.inverse);
                        values = shear.into_iter().flatten().collect();
                    }
                    _ => return Err("Unsupported curve role".into()),
                }
                for value in values {
                    output.extend_from_slice(&(math::narrow(value)? as f32).to_le_bytes());
                }
            }
            self.b.write(data, &output)?;
        }
        self.b.reference(header.at(8), Some(data))?;
        Ok(())
    }
    pub fn group(&mut self, id: usize) -> Result<Address> {
        let g = self.g;
        let header = self.body(id, "TrackGroup")?;
        if !self.written.insert(header) {
            return Ok(header);
        }
        let p = self.field(header, "TrackGroup", "Name")?;
        self.string(p, g.text(id, "name")?)?;
        let vectors = g.ids(id, "vectors")?;
        if let Some(a) = self.array(
            header,
            "TrackGroup",
            "VectorTracks",
            "VectorTrack",
            id,
            "vectors",
            vectors.len(),
        )? {
            let sid = self.r.named("VectorTrack")?;
            let stride = self.r.layout(sid)?.size;
            for (j, track) in vectors.into_iter().enumerate() {
                let row = a.at(j * stride);
                let p = self.field(row, "VectorTrack", "Name")?;
                self.string(p, g.text(track, "name")?)?;
                let key = if matches!(g.field(track, "track_key")?, Value::Null) {
                    let identity = g.nodes[track].identity;
                    if let Some(key) = self.vector_keys.get(&identity) {
                        *key
                    } else {
                        let key = crate::vector_keys::resolve(g, track)?;
                        self.vector_keys.insert(identity, key);
                        key
                    }
                } else {
                    u32::try_from(g.int(track, "track_key")?)
                        .map_err(|_| "Vector key exceeds uint32")?
                };
                let p = self.field(row, "VectorTrack", "TrackKey")?;
                self.b.u32(p, key as usize)?;
                let curve = g.id(track, "curve")?;
                let p = self.field(row, "VectorTrack", "Dimension")?;
                self.b
                    .i32(p, buffer(g, g.id(curve, "controls")?)?.width as i64)?;
                let p = self.field(row, "VectorTrack", "ValueCurve")?;
                self.curve(p, curve, "vector")?;
            }
        }
        let mut tracks = g.ids(id, "transforms")?;
        if g.int(id, "flags")? & 2 != 0 {
            tracks.sort_by(|a, b| {
                g.text(*a, "name")
                    .unwrap()
                    .as_bytes()
                    .cmp(g.text(*b, "name").unwrap().as_bytes())
            });
        }
        if let Some(a) = self.array(
            header,
            "TrackGroup",
            "TransformTracks",
            "TransformTrack",
            id,
            "transforms",
            tracks.len(),
        )? {
            let sid = self.r.named("TransformTrack")?;
            let stride = self.r.layout(sid)?.size;
            for (j, track) in tracks.into_iter().enumerate() {
                let row = a.at(j * stride);
                let p = self.field(row, "TransformTrack", "Name")?;
                self.string(p, g.text(track, "name")?)?;
                let p = self.field(row, "TransformTrack", "Flags")?;
                self.b.i32(p, g.int(track, "flags")?)?;
                for (field, name) in [
                    ("PositionCurve", "position"),
                    ("OrientationCurve", "orientation"),
                    ("ScaleShearCurve", "scale_shear"),
                ] {
                    let p = self.field(row, "TransformTrack", field)?;
                    self.curve(p, g.id(track, name)?, name)?;
                }
            }
        }
        let p = self.field(header, "TrackGroup", "InitialPlacement")?;
        self.transform(p, g.field(id, "placement")?)?;
        let p = self.field(header, "TrackGroup", "AccumulationFlags")?;
        self.b.i32(p, g.int(id, "flags")?)?;
        let p = self.field(header, "TrackGroup", "ExtendedData")?;
        self.variant(p, g.id(id, "metadata")?)?;
        Ok(header)
    }
    pub fn animation(&mut self, id: usize) -> Result<Address> {
        let g = self.g;
        let header = self.body(id, "Animation")?;
        if !self.written.insert(header) {
            return Ok(header);
        }
        let p = self.field(header, "Animation", "Name")?;
        self.string(p, g.text(id, "name")?)?;
        for name in ["Duration", "TimeStep", "Oversampling"] {
            let p = self.field(header, "Animation", name)?;
            self.b.f32(
                p,
                g.real(
                    id,
                    match name {
                        "Duration" => "duration",
                        "TimeStep" => "time_step",
                        _ => "oversampling",
                    },
                )?,
            )?;
        }
        let p = self.field(header, "Animation", "DefaultLoopCount")?;
        self.b.i32(p, g.int(id, "default_loop_count")?)?;
        let p = self.field(header, "Animation", "Flags")?;
        self.b.i32(p, g.int(id, "flags")?)?;
        let p = self.field(header, "Animation", "ExtendedData")?;
        self.variant(p, g.id(id, "metadata")?)?;
        let groups = g.ids(id, "track_groups")?;
        let p = self.field(header, "Animation", "TrackGroups")?;
        self.b.i32(p, groups.len() as i64)?;
        let array = if groups.is_empty() {
            None
        } else {
            Some(
                self.b
                    .alloc(groups.len() * 8, self.o.objects, 4, Storage::Word)?,
            )
        };
        self.b.reference(p.at(4), array)?;
        if let Some(a) = array {
            for (j, group) in groups.into_iter().enumerate() {
                let destination = self.group(group)?;
                self.b.reference(a.at(j * 8), Some(destination))?;
            }
        }
        Ok(header)
    }
    pub fn build(mut self) -> Result<Vec<u8>> {
        let g = self.g;
        let root = g.root;
        let header = self.body(root, "FileInfo")?;
        let schema = self.r.named("FileInfo")?;
        let root_type = self.ty(schema)?;
        let art = g.id(root, "art_tool")?;
        let exporter = g.id(root, "exporter")?;
        let c = g.id(root, "conversion")?;
        let a = self.body(art, "ArtToolInfo")?;
        let e = self.body(exporter, "ExporterInfo")?;
        self.b.reference(header, Some(a))?;
        self.b.reference(header.at(8), Some(e))?;
        self.string(header.at(16), g.text(root, "file_name")?)?;
        self.string(a, g.text(art, "name")?)?;
        for (i, v) in [g.int(art, "major")?, g.int(art, "minor")?, 64]
            .into_iter()
            .enumerate()
        {
            self.b.i32(a.at(8 + i * 4), v)?;
        }
        self.b.f32(a.at(20), g.real(c, "target_units_per_meter")?)?;
        for (i, name) in ["right", "up", "back"].into_iter().enumerate() {
            let values = math::three(g.field(c, name)?)?;
            for (j, v) in values.into_iter().enumerate() {
                self.b.f32(a.at(36 + i * 12 + j * 4), v)?;
            }
        }
        self.string(e, g.text(exporter, "name")?)?;
        let version = g.list(exporter, "version")?;
        if version.len() != 3 {
            return Err("Exporter version requires three integers".into());
        }
        for (i, v) in [
            version[0].int()?,
            version[1].int()?,
            g.int(exporter, "customization")?,
            version[2].int()?,
        ]
        .into_iter()
        .enumerate()
        {
            self.b.i32(e.at(8 + i * 4), v)?;
        }
        self.variant(header.at(132), g.id(root, "metadata")?)?;
        for (field, name) in [
            ("Textures", "textures"),
            ("Materials", "materials"),
            ("Skeletons", "skeletons"),
            ("VertexDatas", "vertex_data"),
            ("TriTopologies", "topologies"),
            ("Meshes", "meshes"),
            ("Models", "models"),
            ("TrackGroups", "track_groups"),
            ("Animations", "animations"),
        ] {
            let items = g.ids(root, name)?;
            let p = self.field(header, "FileInfo", field)?;
            self.b.i32(p, items.len() as i64)?;
            let array = if items.is_empty() {
                None
            } else {
                Some(
                    self.b
                        .alloc(items.len() * 8, self.o.objects, 4, Storage::Word)?,
                )
            };
            self.b.reference(p.at(4), array)?;
            if let Some(array) = array {
                for (j, item) in items.into_iter().enumerate() {
                    let target = match name {
                        "textures" => self.texture(item)?,
                        "materials" => self.material(item)?,
                        "skeletons" => self.skeleton(item)?,
                        "vertex_data" => self.vertices(item)?,
                        "topologies" => self.topology(item)?,
                        "meshes" => self.mesh(item)?,
                        "models" => self.model(item)?,
                        "track_groups" => self.group(item)?,
                        "animations" => self.animation(item)?,
                        _ => unreachable!(),
                    };
                    self.b.reference(array.at(j * 8), Some(target))?;
                }
            }
        }
        self.b.build(root_type, header)
    }
}
