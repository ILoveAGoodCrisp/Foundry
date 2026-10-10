use crate::input::{Graph, Result};
use crate::math::{matrix, narrow};
use std::collections::{HashMap, HashSet};

pub struct Buffer<'a> {
    pub scalar: &'a str,
    pub width: usize,
    pub count: usize,
    pub bytes: &'a [u8],
}
impl Buffer<'_> {
    pub fn unit(&self) -> usize {
        match self.scalar {
            "uint8" | "normal_uint8" => 1,
            "uint16" => 2,
            _ => 4,
        }
    }
    pub fn real(&self, index: usize) -> f64 {
        f32::from_le_bytes(self.bytes[index * 4..index * 4 + 4].try_into().unwrap()) as f64
    }
    pub fn index(&self, index: usize) -> i64 {
        match self.scalar {
            "int32" => {
                i32::from_le_bytes(self.bytes[index * 4..index * 4 + 4].try_into().unwrap()) as i64
            }
            "uint16" => {
                u16::from_le_bytes(self.bytes[index * 2..index * 2 + 2].try_into().unwrap()) as i64
            }
            _ => self.bytes[index] as i64,
        }
    }
    pub fn range(&self) -> (i64, i64) {
        let mut lo = i64::MAX;
        let mut hi = i64::MIN;
        for i in 0..self.count * self.width {
            let v = self.index(i);
            lo = lo.min(v);
            hi = hi.max(v);
        }
        (lo, hi)
    }
}
pub fn buffer(g: &Graph, n: usize) -> Result<Buffer<'_>> {
    let scalar = g.text(n, "scalar")?;
    if !matches!(
        scalar,
        "real32" | "int32" | "uint8" | "normal_uint8" | "uint16"
    ) {
        return Err("Unknown buffer scalar".into());
    }
    let width = usize::try_from(g.int(n, "width")?).map_err(|_| "Invalid buffer width")?;
    let count = usize::try_from(g.int(n, "count")?).map_err(|_| "Invalid buffer count")?;
    let result = Buffer {
        scalar,
        width,
        count,
        bytes: g.bytes(n, "data")?,
    };
    if width == 0
        || width > i32::MAX as usize
        || count > i32::MAX as usize
        || count
            .checked_mul(width)
            .and_then(|v| v.checked_mul(result.unit()))
            != Some(result.bytes.len())
    {
        return Err("Numeric buffer shape does not match owned bytes".into());
    }
    Ok(result)
}
pub fn vertices_count(g: &Graph, id: usize) -> Result<usize> {
    let attrs = g.ids(id, "attributes")?;
    buffer(
        g,
        g.id(
            *attrs.first().ok_or("Vertex data has no attributes")?,
            "buffer",
        )?,
    )
    .map(|v| v.count)
}
pub fn validate(g: &Graph) -> Result<HashMap<usize, (i64, i64)>> {
    let mut ranges = HashMap::new();
    for (id, node) in g.nodes.iter().enumerate() {
        if node.kind == "Buffer" {
            let b = buffer(g, id)?;
            if b.scalar == "real32" {
                if (0..b.count * b.width).any(|i| !b.real(i).is_finite()) {
                    return Err("Numeric buffers must contain finite values".into());
                }
            } else {
                ranges.insert(id, b.range());
            }
        }
    }
    for (id, node) in g.nodes.iter().enumerate() {
        match node.kind.as_str() {
            "VertexData" => {
                let attrs = g.ids(id, "attributes")?;
                let count = vertices_count(g, id)?;
                let mut names = HashMap::new();
                for a in attrs {
                    let name = g.text(a, "name")?;
                    let b = buffer(g, g.id(a, "buffer")?)?;
                    if b.count != count || names.insert(name, (b.scalar, b.width)).is_some() {
                        return Err(
                            "Vertex attributes must have unique names and common count".into()
                        );
                    }
                    if matches!(name, "Position" | "Normal" | "Tangent" | "Binormal")
                        && (b.scalar != "real32" || b.width != 3)
                    {
                        return Err("Spatial attributes require three float32 components".into());
                    }
                }
                if names.get("Position") != Some(&("real32", 3)) {
                    return Err("Geometry requires float32 Position".into());
                }
                match (names.get("BoneWeights"), names.get("BoneIndices")) {
                    (None, None) => {}
                    (Some(&("normal_uint8", 4)), Some(&("uint8", 4))) => {}
                    _ => {
                        return Err(
                            "Skinning requires four normalized byte weights and byte indices"
                                .into(),
                        )
                    }
                };
                matrix(g.field(id, "placement")?)?;
            }
            "Topology" => {
                let indices = g.id(id, "indices")?;
                let b = buffer(g, indices)?;
                if !matches!(b.scalar, "int32" | "uint16") || b.width != 1 || b.count % 3 != 0 {
                    return Err("Topology requires triples of int32 or uint16 indices".into());
                }
                if ranges[&indices].0 < 0 {
                    return Err("Triangle indices cannot be negative".into());
                }
                let count = (b.count / 3) as i64;
                for a in g.ids(id, "groups")? {
                    let first = g.int(a, "first_triangle")?;
                    let size = g.int(a, "triangle_count")?;
                    if g.int(a, "material_index")? < 0
                        || first < 0
                        || size < 0
                        || first.checked_add(size).is_none_or(|end| end > count)
                    {
                        return Err("Material group is outside topology".into());
                    }
                }
                for a in g.ids(id, "annotations")? {
                    let b = buffer(g, g.id(a, "buffer")?)?;
                    if !matches!(b.scalar, "real32" | "int32") {
                        return Err("Invalid annotation scalar".into());
                    }
                    if let Some(remap) = g.opt(a, "indices")? {
                        let rb = buffer(g, remap)?;
                        let (lo, hi) = *ranges
                            .get(&remap)
                            .ok_or("Annotation indices must be integers")?;
                        if rb.scalar != "int32"
                            || rb.width != 1
                            || rb.count != count as usize
                            || lo < 0
                            || hi >= b.count as i64
                        {
                            return Err("Annotation index map is outside its records".into());
                        }
                    } else if b.count != count as usize {
                        return Err("Annotation count must match triangle count".into());
                    }
                }
            }
            "Mesh" => {
                let vertices = g.id(id, "vertices")?;
                if g.boolean(vertices, "data_is_deltas")? {
                    return Err("Primary vertices cannot be delta buffers".into());
                }
                let count = vertices_count(g, vertices)?;
                let topology = g.id(id, "topology")?;
                if ranges
                    .get(&g.id(topology, "indices")?)
                    .ok_or("Triangle indices must be integers")?
                    .1
                    >= count as i64
                {
                    return Err("Triangle index is outside vertex array".into());
                }
                let materials = g.ids(id, "materials")?;
                if !materials.is_empty() {
                    for group in g.ids(topology, "groups")? {
                        if g.int(group, "material_index")? >= materials.len() as i64 {
                            return Err("Material group references absent binding".into());
                        }
                    }
                }
                let attrs = g.ids(vertices, "attributes")?;
                let lookup = |name: &str| -> Result<Option<usize>> {
                    for a in &attrs {
                        if g.text(*a, "name")? == name {
                            return Ok(Some(g.id(*a, "buffer")?));
                        }
                    }
                    Ok(None)
                };
                if let (Some(w), Some(i)) = (lookup("BoneWeights")?, lookup("BoneIndices")?) {
                    let weights = buffer(g, w)?;
                    let indices = buffer(g, i)?;
                    let palette = g.list(id, "bone_bindings")?.len();
                    for (w, i) in weights.bytes.iter().zip(indices.bytes) {
                        if *w != 0 && *i as usize >= palette {
                            return Err("Weighted bone index is outside binding palette".into());
                        }
                    }
                }
                for morph in g.ids(id, "morph_targets")? {
                    if vertices_count(g, g.id(morph, "vertex_data")?)? != count {
                        return Err("Morph count must match primary vertices".into());
                    }
                }
            }
            "Bone" => {
                matrix(g.field(id, "local_matrix")?)?;
                matrix(g.field(id, "world_matrix")?)?;
                narrow(g.real(id, "lod_error")?)?;
            }
            "Skeleton" => {
                let bones = g.ids(id, "bones")?;
                for (i, bone) in bones.iter().enumerate() {
                    let p = g.int(*bone, "parent_index")?;
                    if p < -1 || p >= bones.len() as i64 || p == i as i64 {
                        return Err("Invalid skeleton parent index".into());
                    }
                    let mut seen = HashSet::from([i]);
                    let mut parent = p;
                    while parent >= 0 {
                        let index = parent as usize;
                        if !seen.insert(index) {
                            return Err("Skeleton hierarchy has a cycle".into());
                        }
                        parent = g.int(bones[index], "parent_index")?;
                        if parent < -1 || parent >= bones.len() as i64 {
                            return Err("Invalid skeleton parent index".into());
                        }
                    }
                }
            }
            "Model" => {
                let skeleton = g.id(id, "skeleton")?;
                let names = g
                    .ids(skeleton, "bones")?
                    .into_iter()
                    .map(|b| g.text(b, "name"))
                    .collect::<Result<HashSet<_>>>()?;
                for item in g.list(id, "meshes")? {
                    if let Some(mesh) = item.optional_ref()? {
                        for name in g.list(mesh, "bone_bindings")? {
                            if !names.contains(name.text()?) {
                                return Err("Model mesh binding is absent from skeleton".into());
                            }
                        }
                    }
                }
                matrix(g.field(id, "placement")?)?;
            }
            "Texture" => {
                if g.text(id, "requested_encoding")? != "rgba" {
                    return Err("Compressed texture requests are unsupported".into());
                }
                let images = g.ids(id, "images")?;
                if images.is_empty() {
                    return Err("Texture requires an image".into());
                }
                let first = images[0];
                for image in images {
                    let w = g.int(image, "width")?;
                    let h = g.int(image, "height")?;
                    let stride = g.int(image, "stride")?;
                    if w <= 0
                        || h <= 0
                        || w.checked_mul(4).is_none_or(|row| stride < row)
                        || stride.checked_mul(h) != Some(g.bytes(image, "rgba")?.len() as i64)
                        || w != g.int(first, "width")?
                        || h != g.int(first, "height")?
                    {
                        return Err("Texture image dimensions or stride are invalid".into());
                    }
                }
            }
            "TransformTrack" => {
                let mut counts = HashSet::new();
                for (name, width) in [("position", 3), ("orientation", 4), ("scale_shear", 9)] {
                    let b = buffer(g, g.id(g.id(id, name)?, "controls")?)?;
                    if b.scalar != "real32"
                        || b.width != width
                        || b.count == 0
                        || b.count * b.width > i32::MAX as usize
                    {
                        return Err("Transform tracks require nonempty float32 widths 3/4/9".into());
                    }
                    counts.insert(b.count);
                    if name == "orientation" {
                        for row in 0..b.count {
                            let length = (0..4).map(|k| b.real(row * 4 + k).powi(2)).sum::<f64>();
                            if (length - 1.).abs() > 1e-3 {
                                return Err("Orientation samples must be unit quaternions".into());
                            }
                        }
                    }
                }
                if counts.len() != 1 {
                    return Err("Transform track component counts differ".into());
                }
                i32::try_from(g.int(id, "flags")?).map_err(|_| "Track flags exceed int32")?;
            }
            "VectorTrack" => {
                let b = buffer(g, g.id(g.id(id, "curve")?, "controls")?)?;
                if b.scalar != "real32"
                    || !(1..=16).contains(&b.width)
                    || b.count == 0
                    || b.count * b.width > i32::MAX as usize
                {
                    return Err(
                        "Vector tracks require nonempty float32 dimensions 1 through 16".into(),
                    );
                }
                if !matches!(g.field(id, "track_key")?, crate::input::Value::Null) {
                    u32::try_from(g.int(id, "track_key")?)
                        .map_err(|_| "Vector key exceeds uint32")?;
                }
            }
            "TrackGroup" => {
                let mut names = HashSet::new();
                let mut counts = HashSet::new();
                for track in g.ids(id, "transforms")? {
                    if !names.insert(g.text(track, "name")?) {
                        return Err("Duplicate transform track name".into());
                    }
                    counts.insert(buffer(g, g.id(g.id(track, "position")?, "controls")?)?.count);
                }
                for track in g.ids(id, "vectors")? {
                    counts.insert(buffer(g, g.id(g.id(track, "curve")?, "controls")?)?.count);
                }
                if counts.len() > 1 {
                    return Err("Track group sample counts differ".into());
                }
                i32::try_from(g.int(id, "flags")?).map_err(|_| "Group flags exceed int32")?;
                matrix(g.field(id, "placement")?)?;
            }
            "Animation" => {
                if narrow(g.real(id, "duration")?)? < 0.
                    || narrow(g.real(id, "time_step")?)? <= 0.
                    || narrow(g.real(id, "oversampling")?)? <= 0.
                {
                    return Err("Animation requires nonnegative duration and positive timestep/oversampling".into());
                }
                i32::try_from(g.int(id, "flags")?).map_err(|_| "Animation flags exceed int32")?;
                i32::try_from(g.int(id, "default_loop_count")?)
                    .map_err(|_| "Loop count exceeds int32")?;
            }
            _ => {}
        }
    }
    Ok(ranges)
}
