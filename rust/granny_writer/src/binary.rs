use crate::input::Result;
use std::collections::{BTreeSet, HashMap};

#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash, PartialOrd, Ord)]
pub struct Address {
    pub block: usize,
    pub offset: usize,
}
impl Address {
    pub fn at(self, offset: usize) -> Self {
        Self {
            offset: self.offset + offset,
            ..self
        }
    }
}
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Storage {
    Word,
    Half,
    Byte,
    Mixed,
}
pub struct Block {
    pub data: Vec<u8>,
    pub section: usize,
    pub alignment: usize,
    pub storage: Storage,
    pointers: BTreeSet<usize>,
}
pub struct Builder {
    pub blocks: Vec<Block>,
    pub count: usize,
    budget: usize,
    references: Vec<(Address, Option<Address>)>,
    mixed: Vec<(Address, usize, Address, usize)>,
    strings: HashMap<(usize, String), Address>,
}
fn align(value: usize, alignment: usize) -> Result<usize> {
    if !alignment.is_power_of_two() {
        return Err("Alignment must be a positive power of two".into());
    }
    value
        .checked_add(alignment - 1)
        .map(|v| v & !(alignment - 1))
        .ok_or("Alignment exceeds file limit".into())
}
fn u32value(value: usize) -> Result<u32> {
    u32::try_from(value).map_err(|_| "Value exceeds uint32 file limit".into())
}
impl Builder {
    pub fn new(count: usize) -> Result<Self> {
        if !(1..=256).contains(&count) {
            return Err("Section count must be between 1 and 256".into());
        }
        Ok(Self {
            blocks: Vec::new(),
            count,
            budget: 104 + 44 * count,
            references: Vec::new(),
            mixed: Vec::new(),
            strings: HashMap::new(),
        })
    }
    fn charge(&mut self, size: usize) -> Result<()> {
        self.budget = self
            .budget
            .checked_add(size)
            .ok_or("GR2 allocations exceed file limit")?;
        u32value(self.budget)?;
        Ok(())
    }
    pub fn alloc(
        &mut self,
        size: usize,
        section: usize,
        alignment: usize,
        storage: Storage,
    ) -> Result<Address> {
        if size == 0 || section >= self.count {
            return Err("Allocation requires nonempty size and valid section".into());
        }
        align(0, alignment)?;
        u32value(size)?;
        let unit = match storage {
            Storage::Word => 4,
            Storage::Half => 2,
            _ => 1,
        };
        if !size.is_multiple_of(unit) {
            return Err("Allocation does not match marshalling width".into());
        }
        self.charge(
            size.checked_add(alignment - 1)
                .ok_or("Allocation size overflow")?,
        )?;
        let mut data = Vec::new();
        data.try_reserve_exact(size)
            .map_err(|_| "Cannot allocate GR2 buffer")?;
        data.resize(size, 0);
        let address = Address {
            block: self.blocks.len(),
            offset: 0,
        };
        self.blocks.push(Block {
            data,
            section,
            alignment,
            storage,
            pointers: BTreeSet::new(),
        });
        Ok(address)
    }
    pub fn write(&mut self, address: Address, bytes: &[u8]) -> Result<()> {
        let block = self
            .blocks
            .get_mut(address.block)
            .ok_or("Unowned allocation")?;
        let end = address
            .offset
            .checked_add(bytes.len())
            .ok_or("Write size overflow")?;
        let target = block
            .data
            .get_mut(address.offset..end)
            .ok_or("Write outside allocation")?;
        target.copy_from_slice(bytes);
        Ok(())
    }
    pub fn i32(&mut self, a: Address, v: i64) -> Result<()> {
        let n = i32::try_from(v).map_err(|_| "Value must fit int32")?;
        self.write(a, &n.to_le_bytes())
    }
    pub fn u32(&mut self, a: Address, v: usize) -> Result<()> {
        self.write(a, &u32value(v)?.to_le_bytes())
    }
    pub fn f32(&mut self, a: Address, v: f64) -> Result<()> {
        let n = v as f32;
        if !n.is_finite() {
            return Err("Value is outside finite float32 range".into());
        }
        self.write(a, &n.to_le_bytes())
    }
    pub fn string(&mut self, value: &str, section: usize) -> Result<Address> {
        if value.contains('\0') {
            return Err("Strings cannot contain embedded NUL".into());
        }
        let key = (section, value.to_owned());
        if let Some(a) = self.strings.get(&key) {
            return Ok(*a);
        }
        let a = self.alloc(value.len() + 1, section, 1, Storage::Byte)?;
        self.write(a, value.as_bytes())?;
        self.strings.insert(key, a);
        Ok(a)
    }
    pub fn reference(&mut self, source: Address, target: Option<Address>) -> Result<()> {
        if let Some(a) = target {
            if self
                .blocks
                .get(a.block)
                .is_none_or(|b| a.offset >= b.data.len())
            {
                return Err("Reference target outside allocation".into());
            }
        }
        let b = self
            .blocks
            .get_mut(source.block)
            .ok_or("Unowned pointer allocation")?;
        if source
            .offset
            .checked_add(8)
            .is_none_or(|end| end > b.data.len())
        {
            return Err("Pointer field outside allocation".into());
        }
        if b.pointers
            .range(source.offset.saturating_sub(7)..=source.offset + 7)
            .next()
            .is_some()
        {
            return Err("Pointer fields overlap or repeat".into());
        }
        b.pointers.insert(source.offset);
        if target.is_some() {
            self.charge(12)?;
        }
        self.references.push((source, target));
        Ok(())
    }
    pub fn mixed(&mut self, a: Address, count: usize, kind: Address, stride: usize) -> Result<()> {
        let block = self.blocks.get(a.block).ok_or("Unowned mixed allocation")?;
        if count == 0 || stride == 0 || block.storage != Storage::Mixed {
            return Err("Invalid mixed marshalling range".into());
        }
        if count
            .checked_mul(stride)
            .and_then(|size| a.offset.checked_add(size))
            .is_none_or(|end| end > block.data.len())
        {
            return Err("Mixed marshalling exceeds allocation".into());
        }
        if self
            .blocks
            .get(kind.block)
            .is_none_or(|b| kind.offset >= b.data.len())
        {
            return Err("Mixed schema outside allocation".into());
        }
        self.charge(16)?;
        self.mixed.push((a, count, kind, stride));
        Ok(())
    }
    pub fn build(self, root_type: Address, root: Address) -> Result<Vec<u8>> {
        struct Section {
            size: usize,
            alignment: usize,
            half: usize,
            byte: usize,
            data: usize,
            ptr: usize,
            mar: usize,
            refs: Vec<[u32; 3]>,
            mixed: Vec<[u32; 4]>,
        }
        let mut offsets = vec![0; self.blocks.len()];
        let mut sections = Vec::new();
        for section in 0..self.count {
            let alignment = self
                .blocks
                .iter()
                .filter(|b| b.section == section)
                .map(|b| b.alignment)
                .max()
                .unwrap_or(4)
                .max(4);
            let mut cursor = 0;
            let mut edges = [0; 2];
            for group in 0..3 {
                for (index, block) in self.blocks.iter().enumerate() {
                    let class = match block.storage {
                        Storage::Word | Storage::Mixed => 0,
                        Storage::Half => 1,
                        Storage::Byte => 2,
                    };
                    if block.section == section && class == group {
                        cursor = align(cursor, block.alignment)?;
                        offsets[index] = cursor;
                        cursor = cursor
                            .checked_add(block.data.len())
                            .ok_or("Section size overflow")?;
                    }
                }
                match group {
                    0 => {
                        cursor = align(cursor, 4)?;
                        edges[0] = cursor;
                    }
                    1 => {
                        cursor = align(cursor, 2)?;
                        edges[1] = cursor;
                    }
                    _ => {}
                }
            }
            sections.push(Section {
                size: align(cursor, alignment)?,
                alignment,
                half: edges[0],
                byte: edges[1],
                data: 0,
                ptr: 0,
                mar: 0,
                refs: Vec::new(),
                mixed: Vec::new(),
            });
        }
        let location = |a: Address| -> Result<[u32; 2]> {
            let block = self.blocks.get(a.block).ok_or("Unowned address")?;
            if a.offset >= block.data.len() {
                return Err("Address outside allocation".into());
            }
            Ok([
                u32value(block.section)?,
                u32value(offsets[a.block] + a.offset)?,
            ])
        };
        for (source, target) in &self.references {
            if let Some(destination) = target {
                let [s, o] = location(*destination)?;
                sections[self.blocks[source.block].section].refs.push([
                    u32value(offsets[source.block] + source.offset)?,
                    s,
                    o,
                ]);
            }
        }
        for (source, count, kind, _) in &self.mixed {
            let [s, o] = location(*kind)?;
            sections[self.blocks[source.block].section].mixed.push([
                u32value(*count)?,
                u32value(offsets[source.block] + source.offset)?,
                s,
                o,
            ]);
        }
        let mut cursor = 104 + 44 * self.count;
        for section in &mut sections {
            section.refs.sort();
            section.mixed.sort_by_key(|r| (r[1], r[0], r[2], r[3]));
            cursor = align(cursor, section.alignment)?;
            section.data = cursor;
            cursor += section.size;
            section.ptr = if section.refs.is_empty() { 0 } else { cursor };
            cursor += section.refs.len() * 12;
            section.mar = if section.mixed.is_empty() { 0 } else { cursor };
            cursor += section.mixed.len() * 16;
            u32value(cursor)?;
        }
        let mut result = Vec::new();
        result
            .try_reserve_exact(cursor)
            .map_err(|_| "Cannot allocate final GR2")?;
        result.resize(cursor, 0);
        fn words(output: &mut [u8], offset: usize, values: &[u32]) {
            for (i, value) in values.iter().enumerate() {
                output[offset + i * 4..offset + i * 4 + 4].copy_from_slice(&value.to_le_bytes());
            }
        }
        words(
            &mut result,
            0,
            &[
                0x5e499be5,
                0x141f636f,
                0xa9eb131e,
                0xc4edbe90,
                u32value(104 + 44 * self.count)?,
                0,
                0,
                0,
            ],
        );
        let [ts, to] = location(root_type)?;
        let [os, oo] = location(root)?;
        words(
            &mut result,
            32,
            &[
                7,
                u32value(cursor)?,
                0,
                72,
                u32value(self.count)?,
                ts,
                to,
                os,
                oo,
                0x80000037,
                0,
                0,
                0,
                0,
                0,
                0,
                0,
                0,
            ],
        );
        for (i, section) in sections.iter().enumerate() {
            words(
                &mut result,
                104 + i * 44,
                &[
                    0,
                    u32value(section.data)?,
                    u32value(section.size)?,
                    u32value(section.size)?,
                    u32value(section.alignment)?,
                    u32value(section.half)?,
                    u32value(section.byte)?,
                    u32value(section.ptr)?,
                    u32value(section.refs.len())?,
                    u32value(section.mar)?,
                    u32value(section.mixed.len())?,
                ],
            );
            for (j, record) in section.refs.iter().enumerate() {
                words(&mut result, section.ptr + j * 12, record);
            }
            for (j, record) in section.mixed.iter().enumerate() {
                words(&mut result, section.mar + j * 16, record);
            }
        }
        for (i, block) in self.blocks.iter().enumerate() {
            let start = sections[block.section].data + offsets[i];
            result[start..start + block.data.len()].copy_from_slice(&block.data);
        }
        for (a, _) in &self.references {
            let start = sections[self.blocks[a.block].section].data + offsets[a.block] + a.offset;
            result[start..start + 8].fill(0);
        }
        let checksum = crc32fast::hash(&result[104..]);
        words(&mut result, 40, &[checksum]);
        Ok(result)
    }
}
