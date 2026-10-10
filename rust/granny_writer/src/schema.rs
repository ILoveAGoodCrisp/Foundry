use crate::binary::Storage;
use crate::input::{Graph, Result};
use serde::Deserialize;
use std::collections::{HashMap, HashSet};

#[derive(Clone, Debug, Deserialize, PartialEq, Eq, Hash)]
pub struct Member {
    pub name: String,
    pub kind: u32,
    pub width: usize,
    pub reference: Option<String>,
    pub extra: [i32; 3],
}
#[derive(Clone, Debug, Deserialize)]
pub struct Schema {
    pub name: String,
    pub members: Vec<Member>,
}
#[derive(Clone, Debug)]
pub struct Layout {
    pub size: usize,
    pub offsets: Vec<usize>,
    pub storage: Storage,
    pub mask: u32,
}
pub struct Registry {
    pub schemas: Vec<Schema>,
    names: HashMap<String, usize>,
    pool: HashMap<Vec<Member>, usize>,
    layouts: HashMap<usize, Layout>,
    metadata: HashMap<usize, usize>,
    active: HashSet<usize>,
}
impl Registry {
    pub fn new() -> Result<Self> {
        let definitions: Vec<Schema> = serde_json::from_str(include_str!("standard_schemas.json"))
            .map_err(|e| e.to_string())?;
        let mut result = Self {
            schemas: Vec::new(),
            names: HashMap::new(),
            pool: HashMap::new(),
            layouts: HashMap::new(),
            metadata: HashMap::new(),
            active: HashSet::new(),
        };
        for s in definitions {
            result.define(s.name, s.members)?;
        }
        Ok(result)
    }
    pub fn define(&mut self, name: String, members: Vec<Member>) -> Result<usize> {
        if self.names.contains_key(&name) {
            return Err(format!("Duplicate schema {name}"));
        }
        let id = if let Some(id) = self.pool.get(&members) {
            *id
        } else {
            let id = self.schemas.len();
            self.schemas.push(Schema {
                name: name.clone(),
                members: members.clone(),
            });
            self.pool.insert(members, id);
            id
        };
        self.names.insert(name, id);
        Ok(id)
    }
    pub fn named(&self, name: &str) -> Result<usize> {
        self.names
            .get(name)
            .copied()
            .ok_or_else(|| format!("Unknown schema {name}"))
    }
    pub fn intern(&mut self, members: Vec<Member>) -> Result<usize> {
        if let Some(id) = self.pool.get(&members) {
            return Ok(*id);
        }
        self.define(format!("dynamic_{:04}", self.schemas.len()), members)
    }
    pub fn member(name: &str, kind: u32, width: usize, reference: Option<String>) -> Member {
        Member {
            name: name.to_owned(),
            kind,
            width,
            reference,
            extra: [0; 3],
        }
    }
    pub fn layout(&mut self, id: usize) -> Result<Layout> {
        self.layout_inner(id, &mut HashSet::new())
    }
    fn layout_inner(&mut self, id: usize, active: &mut HashSet<usize>) -> Result<Layout> {
        if let Some(v) = self.layouts.get(&id) {
            return Ok(v.clone());
        }
        if !active.insert(id) {
            return Err("Recursive inline schema has no finite size".into());
        }
        let mut size = 0usize;
        let mut mask = 0;
        let mut offsets = Vec::new();
        for member in self.schemas[id].members.clone() {
            offsets.push(size);
            let (unit, flags) = match member.kind {
                1 => {
                    let child = self.named(
                        member
                            .reference
                            .as_deref()
                            .ok_or("Inline field lacks schema")?,
                    )?;
                    let layout = self.layout_inner(child, active)?;
                    (layout.size, layout.mask)
                }
                2 | 22 => (8, 0),
                3 | 4 => (12, 4),
                5 => (16, 0),
                7 => (20, 4),
                8 => (8, 4),
                9 => (68, 4),
                10 | 19 | 20 => (4, 4),
                11..=14 => (1, 1),
                15..=18 | 21 => (2, 2),
                _ => return Err("Unsupported schema member kind".into()),
            };
            size = size
                .checked_add(
                    unit.checked_mul(member.width.max(1))
                        .ok_or("Schema width overflow")?,
                )
                .ok_or("Schema size overflow")?;
            if size > u32::MAX as usize {
                return Err("Schema size exceeds uint32".into());
            }
            mask |= flags;
        }
        active.remove(&id);
        let result = Layout {
            size,
            offsets,
            storage: match mask {
                0 | 4 => Storage::Word,
                1 => Storage::Byte,
                2 => Storage::Half,
                _ => Storage::Mixed,
            },
            mask,
        };
        self.layouts.insert(id, result.clone());
        Ok(result)
    }
    pub fn offset(&mut self, id: usize, field: &str) -> Result<usize> {
        let matches: Vec<usize> = self.schemas[id]
            .members
            .iter()
            .enumerate()
            .filter_map(|(i, m)| (m.name == field).then_some(i))
            .collect();
        if matches.len() != 1 {
            return Err(format!("Field {field} is absent or ambiguous"));
        }
        Ok(self.layout(id)?.offsets[matches[0]])
    }
    pub fn metadata(&mut self, g: &Graph, id: usize) -> Result<usize> {
        if let Some(s) = self.metadata.get(&id) {
            return Ok(*s);
        }
        if !self.active.insert(id) {
            return Err("Metadata records must be acyclic".into());
        }
        let mut members = Vec::new();
        for member in g.ids(id, "members")? {
            let name = g.text(member, "name")?;
            let kind = g.text(member, "kind")?;
            let mut reference = None;
            let mut width = 0;
            let tag = match kind {
                "int32" => 19,
                "real32" => 10,
                "string" => 8,
                "int32_array" | "real32_array" => {
                    width = g.list(member, "value")?.len();
                    if width == 0 {
                        return Err("Fixed scalar arrays require positive width".into());
                    }
                    if kind == "int32_array" {
                        19
                    } else {
                        10
                    }
                }
                "reference" => {
                    let child = self.metadata(g, g.id(member, "value")?)?;
                    reference = Some(self.schemas[child].name.clone());
                    2
                }
                "record_array" | "variant_array" => {
                    let mut previous = None;
                    for item in g.list(member, "value")? {
                        let child = self.metadata(g, item.reference()?)?;
                        if kind == "record_array" && previous.is_some_and(|p| p != child) {
                            return Err("Record arrays require homogeneous schemas".into());
                        }
                        previous = Some(child);
                    }
                    7
                }
                _ => return Err(format!("Unsupported metadata kind {kind}")),
            };
            if name.contains('\0') {
                return Err("Metadata names cannot contain NUL".into());
            }
            members.push(Self::member(name, tag, width, reference));
        }
        let result = self.intern(members)?;
        self.active.remove(&id);
        self.metadata.insert(id, result);
        Ok(result)
    }
    pub fn vertex(&mut self, g: &Graph, id: usize) -> Result<usize> {
        let mut members = Vec::new();
        for attribute in g.ids(id, "attributes")? {
            let buffer = g.id(attribute, "buffer")?;
            let kind = match g.text(buffer, "scalar")? {
                "real32" => 10,
                "int32" => 19,
                "uint16" => 16,
                "uint8" => 12,
                "normal_uint8" => 14,
                _ => return Err("Unsupported vertex scalar".into()),
            };
            let width =
                usize::try_from(g.int(buffer, "width")?).map_err(|_| "Invalid vertex width")?;
            if width == 0 {
                return Err("Vertex width must be positive".into());
            }
            members.push(Self::member(g.text(attribute, "name")?, kind, width, None));
        }
        self.intern(members)
    }
    pub fn annotation(&mut self, g: &Graph, id: usize) -> Result<usize> {
        let buffer = g.id(id, "buffer")?;
        let kind = match g.text(buffer, "scalar")? {
            "real32" => 10,
            "int32" => 19,
            _ => return Err("Annotation scalar must be int32 or float32".into()),
        };
        self.intern(vec![Self::member(
            g.text(id, "member_name")?,
            kind,
            usize::try_from(g.int(buffer, "width")?).map_err(|_| "Invalid annotation width")?,
            None,
        )])
    }
}
