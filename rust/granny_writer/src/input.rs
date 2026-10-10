use pyo3::prelude::*;
use pyo3::pybacked::PyBackedBytes;
use pyo3::types::{PyBool, PyBytes, PyFloat, PyInt, PyList, PyString, PyTuple};
use std::collections::{BTreeMap, HashMap};

pub type Result<T> = std::result::Result<T, String>;

#[derive(Debug)]
pub enum Value {
    Null,
    Bool(bool),
    Int(i64),
    Real(f64),
    Text(String),
    Bytes(PyBackedBytes),
    List(Vec<Value>),
    Ref(usize),
}

impl Value {
    pub fn text(&self) -> Result<&str> {
        if let Self::Text(v) = self {
            Ok(v)
        } else {
            Err("Expected text".into())
        }
    }
    pub fn int(&self) -> Result<i64> {
        match self {
            Self::Int(v) => Ok(*v),
            Self::Bool(v) => Ok(i64::from(*v)),
            _ => Err("Expected integer".into()),
        }
    }
    pub fn real(&self) -> Result<f64> {
        match self {
            Self::Real(v) => Ok(*v),
            Self::Int(v) => Ok(*v as f64),
            Self::Bool(v) => Ok(u8::from(*v) as f64),
            _ => Err("Expected real number".into()),
        }
    }
    pub fn boolean(&self) -> Result<bool> {
        if let Self::Bool(v) = self {
            Ok(*v)
        } else {
            Err("Expected boolean".into())
        }
    }
    pub fn list(&self) -> Result<&[Value]> {
        if let Self::List(v) = self {
            Ok(v)
        } else {
            Err("Expected sequence".into())
        }
    }
    pub fn reference(&self) -> Result<usize> {
        if let Self::Ref(v) = self {
            Ok(*v)
        } else {
            Err("Expected export record".into())
        }
    }
    pub fn optional_ref(&self) -> Result<Option<usize>> {
        if matches!(self, Self::Null) {
            Ok(None)
        } else {
            self.reference().map(Some)
        }
    }
    pub fn bytes(&self) -> Result<&[u8]> {
        if let Self::Bytes(v) = self {
            Ok(v)
        } else {
            Err("Expected owned bytes".into())
        }
    }
}

#[derive(Debug)]
pub struct Node {
    pub kind: String,
    pub identity: usize,
    pub fields: BTreeMap<String, Value>,
}
#[derive(Debug)]
pub struct Graph {
    pub nodes: Vec<Node>,
    pub root: usize,
}

impl Graph {
    pub fn field(&self, node: usize, name: &str) -> Result<&Value> {
        self.nodes
            .get(node)
            .and_then(|v| v.fields.get(name))
            .ok_or_else(|| format!("Missing field {name}"))
    }
    pub fn id(&self, n: usize, f: &str) -> Result<usize> {
        self.field(n, f)?.reference()
    }
    pub fn opt(&self, n: usize, f: &str) -> Result<Option<usize>> {
        self.field(n, f)?.optional_ref()
    }
    pub fn text(&self, n: usize, f: &str) -> Result<&str> {
        self.field(n, f)?.text()
    }
    pub fn int(&self, n: usize, f: &str) -> Result<i64> {
        self.field(n, f)?.int()
    }
    pub fn real(&self, n: usize, f: &str) -> Result<f64> {
        self.field(n, f)?.real()
    }
    pub fn boolean(&self, n: usize, f: &str) -> Result<bool> {
        self.field(n, f)?.boolean()
    }
    pub fn list(&self, n: usize, f: &str) -> Result<&[Value]> {
        self.field(n, f)?.list()
    }
    pub fn ids(&self, n: usize, f: &str) -> Result<Vec<usize>> {
        self.list(n, f)?.iter().map(Value::reference).collect()
    }
    pub fn bytes(&self, n: usize, f: &str) -> Result<&[u8]> {
        self.field(n, f)?.bytes()
    }
}

fn fields(kind: &str) -> Result<&'static [&'static str]> {
    Ok(match kind {
        "ExportFile" => &[
            "file_name",
            "art_tool",
            "exporter",
            "conversion",
            "materials",
            "textures",
            "skeletons",
            "vertex_data",
            "topologies",
            "meshes",
            "models",
            "track_groups",
            "animations",
            "metadata",
        ],
        "ArtToolInfo" => &[
            "name",
            "major",
            "minor",
            "pointer_size",
            "units_per_meter",
            "origin",
            "right",
            "up",
            "back",
        ],
        "ExporterInfo" => &["name", "version", "customization"],
        "CoordinateConversion" => &[
            "target_units_per_meter",
            "right",
            "up",
            "back",
            "reflect_y",
            "state",
        ],
        "Buffer" => &["scalar", "width", "count", "data"],
        "Attribute" => &["name", "component_name", "buffer"],
        "VertexData" => &["attributes", "placement", "reflect_y", "data_is_deltas"],
        "Topology" => &[
            "indices",
            "groups",
            "annotations",
            "invert_winding",
            "reflect_winding",
        ],
        "MaterialGroup" => &["material_index", "first_triangle", "triangle_count"],
        "TriangleAnnotation" => &["name", "member_name", "buffer", "map_from_tri", "indices"],
        "Metadata" => &["members"],
        "Member" => &["name", "kind", "value"],
        "Material" => &["name", "metadata", "texture", "maps"],
        "MaterialMap" => &["usage", "material"],
        "Bone" => &[
            "name",
            "parent_index",
            "local_matrix",
            "world_matrix",
            "lod_error",
            "metadata",
        ],
        "Skeleton" => &["name", "bones", "lod_type", "metadata"],
        "Model" => &["name", "skeleton", "meshes", "placement", "metadata"],
        "Mesh" => &[
            "name",
            "vertices",
            "topology",
            "materials",
            "bone_bindings",
            "metadata",
            "morph_targets",
        ],
        "MorphTarget" => &["name", "vertex_data"],
        "SampledCurve" => &["controls"],
        "TransformTrack" => &["name", "position", "orientation", "scale_shear", "flags"],
        "VectorTrack" => &["name", "bone_name", "curve", "track_key"],
        "TrackGroup" => &[
            "name",
            "transforms",
            "vectors",
            "flags",
            "placement",
            "metadata",
        ],
        "Animation" => &[
            "name",
            "duration",
            "time_step",
            "track_groups",
            "oversampling",
            "default_loop_count",
            "flags",
            "metadata",
        ],
        "Texture" => &["name", "images", "requested_encoding"],
        "TextureImage" => &["width", "height", "stride", "rgba"],
        _ => return Err(format!("Unsupported export record {kind}")),
    })
}

struct Reader {
    graph: Graph,
    identities: HashMap<usize, usize>,
    numeric_types: Option<(Py<PyAny>, Py<PyAny>)>,
}
impl Reader {
    fn value(&mut self, object: &Bound<'_, PyAny>, depth: usize) -> PyResult<Value> {
        if depth > 256 {
            return Err(pyo3::exceptions::PyValueError::new_err(
                "Export graph nesting exceeds 256",
            ));
        }
        if object.is_none() {
            return Ok(Value::Null);
        }
        if object.is_instance_of::<PyBool>() {
            return Ok(Value::Bool(object.extract()?));
        }
        if object.is_instance_of::<PyInt>() {
            return Ok(Value::Int(object.extract()?));
        }
        if object.is_instance_of::<PyFloat>() {
            return Ok(Value::Real(object.extract()?));
        }
        if object.is_instance_of::<PyString>() {
            return Ok(Value::Text(object.extract()?));
        }
        if object.is_instance_of::<PyBytes>() {
            return Ok(Value::Bytes(object.extract()?));
        }
        if object.is_instance_of::<PyTuple>() || object.is_instance_of::<PyList>() {
            let length = object.len()?;
            if length >= i32::MAX as usize {
                return Err(pyo3::exceptions::PyValueError::new_err(
                    "Export sequence exceeds int32",
                ));
            }
            let mut values = Vec::with_capacity(length);
            for item in object.try_iter()? {
                values.push(self.value(&item?, depth + 1)?);
            }
            return Ok(Value::List(values));
        }
        let identity = object.as_ptr() as usize;
        if let Some(index) = self.identities.get(&identity) {
            return Ok(Value::Ref(*index));
        }
        let kind = object.get_type().name()?.to_str()?.to_owned();
        let names = match fields(&kind) {
            Ok(names) => names,
            Err(message) => {
                // Blender may supply NumPy scalar values. Use Python's numeric
                // protocol without importing or linking against NumPy itself.
                let py = object.py();
                if self.numeric_types.is_none() {
                    let numbers = py.import("numbers")?;
                    self.numeric_types = Some((
                        numbers.getattr("Integral")?.unbind(),
                        numbers.getattr("Real")?.unbind(),
                    ));
                }
                let (integral, real) = self.numeric_types.as_ref().unwrap();
                if object.is_instance(integral.bind(py))? {
                    return Ok(Value::Int(object.extract()?));
                }
                if object.is_instance(real.bind(py))? {
                    return Ok(Value::Real(object.extract()?));
                }
                return Err(pyo3::exceptions::PyValueError::new_err(message));
            }
        };
        let index = self.graph.nodes.len();
        self.identities.insert(identity, index);
        self.graph.nodes.push(Node {
            kind,
            identity,
            fields: BTreeMap::new(),
        });
        let mut parsed = BTreeMap::new();
        for name in names {
            parsed.insert(
                (*name).to_owned(),
                self.value(&object.getattr(*name)?, depth + 1)?,
            );
        }
        self.graph.nodes[index].fields = parsed;
        Ok(Value::Ref(index))
    }
}

pub fn read(object: &Bound<'_, PyAny>) -> PyResult<Graph> {
    let mut reader = Reader {
        graph: Graph {
            nodes: Vec::new(),
            root: 0,
        },
        identities: HashMap::new(),
        numeric_types: None,
    };
    let root = reader
        .value(object, 0)?
        .reference()
        .map_err(pyo3::exceptions::PyValueError::new_err)?;
    if reader.graph.nodes[root].kind != "ExportFile" {
        return Err(pyo3::exceptions::PyValueError::new_err(
            "Rust writing requires ExportFile records",
        ));
    }
    reader.graph.root = root;
    Ok(reader.graph)
}
