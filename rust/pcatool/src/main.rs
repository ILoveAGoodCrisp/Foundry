//! Tool supplies an uncentered, column-major matrix with eight rows per vertex:
//! position.xyz, normal.xyz, tension.xy. Only positions determine the temporal
//! basis; Tool projects all eight channels onto the returned basis itself.
use nalgebra::{DMatrix, SymmetricEigen};
use std::error::Error;
use std::fs::{self, File, OpenOptions};
use std::io::{BufReader, BufWriter, Read, Write};
use std::path::Path;

type Result<T> = std::result::Result<T, Box<dyn Error>>;

fn read_positions(path: &Path) -> Result<(u32, DMatrix<f64>)> {
    let file = File::open(path)?;
    let size = file.metadata()?.len();
    let mut input = BufReader::new(file);
    let mut header = [0; 8];
    input.read_exact(&mut header)?;
    let rows = u32::from_le_bytes(header[..4].try_into()?);
    let frames = u32::from_le_bytes(header[4..].try_into()?);
    if rows == 0 || rows % 8 != 0 || frames == 0 {
        return Err("expected nonempty matrix with eight rows per vertex".into());
    }
    let expected = u64::from(rows)
        .checked_mul(u64::from(frames))
        .and_then(|n| n.checked_mul(8))
        .and_then(|n| n.checked_add(8))
        .ok_or("matrix dimensions overflow")?;
    if size != expected {
        return Err("matrix length does not match its dimensions".into());
    }
    let coordinates = rows as usize / 8 * 3;
    let count = coordinates
        .checked_mul(frames as usize)
        .ok_or("matrix too large")?;
    let mut positions = Vec::new();
    positions.try_reserve_exact(count)?;
    let mut frame = Vec::new();
    let frame_bytes = (rows as usize).checked_mul(8).ok_or("frame too large")?;
    frame.try_reserve_exact(frame_bytes)?;
    frame.resize(frame_bytes, 0);
    for _ in 0..frames {
        input.read_exact(&mut frame)?;
        for (row, bytes) in frame.chunks_exact(8).enumerate() {
            let value = f64::from_le_bytes(bytes.try_into()?);
            if !value.is_finite() {
                return Err("matrix contains a non-finite value".into());
            }
            if row % 8 < 3 {
                positions.push(value);
            }
        }
    }
    Ok((
        rows,
        DMatrix::from_vec(coordinates, frames as usize, positions),
    ))
}

fn solve(positions: &DMatrix<f64>) -> Result<(DMatrix<f64>, Vec<f64>)> {
    // Do NOT subtract a temporal mean: the input is already relative to the
    // render rest pose, and Tool's protocol has no separate mean-shape field.
    // nalgebra uses an optimized matrix multiply for this dominant operation.
    let gram = positions.transpose() * positions;
    if !gram.iter().all(|v| v.is_finite()) {
        return Err("position covariance overflowed".into());
    }
    let n = gram.nrows();
    let decomposition = SymmetricEigen::try_new(gram, f64::EPSILON, n.saturating_mul(1000))
        .ok_or("eigensolver did not converge")?;
    if !decomposition
        .eigenvalues
        .iter()
        .chain(decomposition.eigenvectors.iter())
        .all(|v| v.is_finite())
    {
        return Err("eigensolver returned non-finite values".into());
    }
    let mut order: Vec<_> = (0..n).collect();
    order.sort_by(|&a, &b| decomposition.eigenvalues[b].total_cmp(&decomposition.eigenvalues[a]));
    let mut basis = DMatrix::zeros(n, n);
    let mut values = Vec::with_capacity(n);
    for (column, &source) in order.iter().enumerate() {
        values.push(decomposition.eigenvalues[source].max(0.0));
        let vector = decomposition.eigenvectors.column(source);
        // Fix the otherwise arbitrary sign for repeatable output.
        let pivot = (0..n)
            .max_by(|&a, &b| vector[a].abs().total_cmp(&vector[b].abs()))
            .unwrap();
        let sign = if vector[pivot] < 0.0 { -1.0 } else { 1.0 };
        for row in 0..n {
            basis[(row, column)] = sign * vector[row];
        }
    }
    Ok((basis, values))
}

fn process(path: &Path) -> Result<()> {
    let (rows, positions) = read_positions(path)?;
    let frames = positions.ncols();
    let (basis, eigenvalues) = solve(&positions)?;
    // Stage a complete response beside the input. Failed validation/solving
    // never truncates Tool's source matrix; rename publishes it atomically.
    let mut temp_name = path.as_os_str().to_os_string();
    temp_name.push(format!(".pcatool-{}.tmp", std::process::id()));
    let temp = Path::new(&temp_name);
    let file = OpenOptions::new().write(true).create_new(true).open(temp)?;
    let result = (|| -> Result<()> {
        let mut output = BufWriter::new(file);
        output.write_all(&rows.to_le_bytes())?;
        output.write_all(&(frames as u32).to_le_bytes())?;
        // DMatrix stores its columns contiguously, as required by Tool.
        for value in basis.iter().chain(eigenvalues.iter()) {
            output.write_all(&value.to_le_bytes())?;
        }
        output.flush()?;
        output.get_ref().sync_all()?;
        drop(output);
        fs::rename(temp, path)?;
        Ok(())
    })();
    if result.is_err() {
        let _ = fs::remove_file(temp);
    }
    result?;
    println!("Foundry PCA: {} vertices, {frames} frames", rows / 8);
    Ok(())
}

fn main() {
    let mut args = std::env::args_os().skip(1);
    let first = args.next();
    if first.as_deref() == Some(std::ffi::OsStr::new("--version")) {
        println!("Foundry pcatool {}", env!("CARGO_PKG_VERSION"));
        return;
    }
    let result = match (first, args.next()) {
        (Some(path), None) => process(Path::new(&path)),
        _ => Err("usage: pcatool.exe <matrix-file>".into()),
    };
    if let Err(error) = result {
        eprintln!("Foundry PCA failed: {error}");
        std::process::exit(1);
    }
}
