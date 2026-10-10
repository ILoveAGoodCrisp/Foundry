//! Portable CRC32 key for a bone-linked event. No SDK or platform calls.
use crate::input::{Graph, Result};
use crc32fast::Hasher;

fn name_bytes(name: &str) -> Result<&[u8]> {
    if name.contains('\0') {
        return Err("Vector-key names cannot contain NUL".into());
    }
    Ok(name.as_bytes())
}

pub fn resolve(g: &Graph, track: usize) -> Result<u32> {
    let name = name_bytes(g.text(track, "name")?)?;
    let bone_name = g.text(track, "bone_name")?;
    let mut resolved = None;
    for (id, node) in g.nodes.iter().enumerate() {
        if node.kind != "Skeleton" {
            continue;
        }
        let bones = g.ids(id, "bones")?;
        for (index, bone) in bones.iter().enumerate() {
            if g.text(*bone, "name")? != bone_name {
                continue;
            }
            let mut crc = Hasher::new();
            let mut ancestor = index as i64;
            let mut depth = 0;
            while ancestor != -1 {
                let index = usize::try_from(ancestor).map_err(|_| "Invalid vector-key ancestor")?;
                let bone = *bones
                    .get(index)
                    .ok_or("Vector key references an absent ancestor bone")?;
                depth += 1;
                if depth > bones.len() {
                    return Err("Vector-key skeleton hierarchy has a cycle".into());
                }
                crc.update(name_bytes(g.text(bone, "name")?)?);
                ancestor = g.int(bone, "parent_index")?;
            }
            crc.update(name);
            let key = crc.finalize();
            if resolved.is_some_and(|other| other != key) {
                return Err("Vector event bone is ambiguous across skeleton hierarchies; supply an authoritative track_key".into());
            }
            resolved = Some(key);
        }
    }
    resolved.ok_or_else(|| format!("Vector event references an absent bone: {bone_name}"))
}
