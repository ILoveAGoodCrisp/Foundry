mod binary;
mod emit;
mod input;
mod math;
mod schema;
mod validate;
mod vector_keys;
use pyo3::prelude::*;
use pyo3::types::PyBytes;
use std::collections::HashMap;

#[pyfunction]
fn inspect_export(data: &Bound<'_, PyAny>) -> PyResult<usize> {
    Ok(input::read(data)?.nodes.len())
}

#[pyfunction]
#[pyo3(signature=(data,section_count=1,type_section=0,object_section=0,string_section=0,buffer_section=None,vector_keys=None))]
// Keep the Python writer's keyword options compatible at this boundary.
#[allow(clippy::too_many_arguments)]
fn build_file<'py>(
    py: Python<'py>,
    data: &Bound<'py, PyAny>,
    section_count: usize,
    type_section: usize,
    object_section: usize,
    string_section: usize,
    buffer_section: Option<usize>,
    vector_keys: Option<HashMap<usize, u32>>,
) -> PyResult<Bound<'py, PyBytes>> {
    let graph = input::read(data)?;
    let options = emit::Options {
        sections: section_count,
        types: type_section,
        objects: object_section,
        strings: string_section,
        buffers: buffer_section.unwrap_or(object_section),
    };
    let result = py
        .detach(move || {
            let mut writer = emit::Writer::new(&graph, options)?;
            writer.vector_keys = vector_keys.unwrap_or_default();
            writer.build()
        })
        .map_err(pyo3::exceptions::PyValueError::new_err)?;
    Ok(PyBytes::new(py, &result))
}

#[pymodule]
fn foundry_granny(module: &Bound<'_, PyModule>) -> PyResult<()> {
    module.add("PROTOCOL_VERSION", 1)?;
    module.add("__version__", env!("CARGO_PKG_VERSION"))?;
    module.add(
        "CAPABILITIES",
        (
            "geometry",
            "skeletons",
            "metadata",
            "animation",
            "textures",
            "vector_keys",
        ),
    )?;
    module.add_function(wrap_pyfunction!(inspect_export, module)?)?;
    module.add_function(wrap_pyfunction!(build_file, module)?)?;
    Ok(())
}
