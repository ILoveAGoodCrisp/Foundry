use crate::input::{Graph, Result, Value};
pub type Matrix = [[f64; 3]; 3];
pub type Mat4 = [[f64; 4]; 4];
pub const ID: Matrix = [[1., 0., 0.], [0., 1., 0.], [0., 0., 1.]];
pub const ID4: Mat4 = [
    [1., 0., 0., 0.],
    [0., 1., 0., 0.],
    [0., 0., 1., 0.],
    [0., 0., 0., 1.],
];
pub const MIRROR: Matrix = [[1., 0., 0.], [0., -1., 0.], [0., 0., 1.]];
pub fn narrow(v: f64) -> Result<f64> {
    let result = v as f32;
    if !result.is_finite() {
        return Err("Transform result is outside finite float32 range".into());
    }
    Ok(result as f64)
}
fn sum(values: impl IntoIterator<Item = f64>) -> f64 {
    let (mut total, mut correction) = (0f64, 0f64);
    for term in values {
        let updated = total + term;
        correction += if total.abs() >= term.abs() {
            (total - updated) + term
        } else {
            (term - updated) + total
        };
        total = updated;
    }
    if correction != 0. && correction.is_finite() {
        total += correction;
    }
    total
}
pub fn vector(m: Matrix, v: [f64; 3]) -> [f64; 3] {
    std::array::from_fn(|i| sum((0..3).map(|k| m[i][k] * v[k])))
}
pub fn transpose(m: Matrix) -> Matrix {
    std::array::from_fn(|i| std::array::from_fn(|j| m[j][i]))
}
pub fn multiply(a: Matrix, b: Matrix) -> Matrix {
    std::array::from_fn(|i| std::array::from_fn(|j| sum((0..3).map(|k| a[i][k] * b[k][j]))))
}
pub fn determinant(m: Matrix) -> f64 {
    let [a, b, c] = m;
    a[0] * (b[1] * c[2] - b[2] * c[1]) - a[1] * (b[0] * c[2] - b[2] * c[0])
        + a[2] * (b[0] * c[1] - b[1] * c[0])
}
pub fn inverse(m: Matrix) -> Result<Matrix> {
    let scale = m.iter().flatten().map(|v| v.abs()).fold(0f64, f64::max);
    if scale == 0. || !scale.is_finite() {
        return Err("Singular or nonfinite linear transform".into());
    }
    let [a, b, c] = m.map(|r| r.map(|v| v / scale));
    let det = determinant([a, b, c]);
    if det.abs() < 1e-12 {
        return Err("Singular or ill-conditioned linear transform".into());
    }
    let co = [
        [
            b[1] * c[2] - b[2] * c[1],
            b[2] * c[0] - b[0] * c[2],
            b[0] * c[1] - b[1] * c[0],
        ],
        [
            c[1] * a[2] - c[2] * a[1],
            c[2] * a[0] - c[0] * a[2],
            c[0] * a[1] - c[1] * a[0],
        ],
        [
            a[1] * b[2] - a[2] * b[1],
            a[2] * b[0] - a[0] * b[2],
            a[0] * b[1] - a[1] * b[0],
        ],
    ];
    Ok(transpose(co.map(|r| r.map(|v| v / det / scale))))
}
pub fn three(v: &Value) -> Result<[f64; 3]> {
    let s = v.list()?;
    if s.len() != 3 {
        return Err("Expected three components".into());
    }
    Ok([s[0].real()?, s[1].real()?, s[2].real()?])
}
pub fn matrix(v: &Value) -> Result<Mat4> {
    let rows = v.list()?;
    if rows.len() != 4 {
        return Err("Expected affine 4x4 matrix".into());
    }
    let mut out = ID4;
    for (i, row) in rows.iter().enumerate() {
        let cols = row.list()?;
        if cols.len() != 4 {
            return Err("Expected affine 4x4 matrix".into());
        }
        for (j, value) in cols.iter().enumerate() {
            out[i][j] = value.real()?;
            if !out[i][j].is_finite() {
                return Err("Matrix must be finite".into());
            }
        }
    }
    if out[3]
        .iter()
        .zip([0., 0., 0., 1.])
        .any(|(a, b)| (a - b).abs() > 1e-7)
    {
        return Err("Matrix must be affine".into());
    }
    inverse(linear(out))?;
    Ok(out)
}
pub fn linear(m: Mat4) -> Matrix {
    std::array::from_fn(|i| std::array::from_fn(|j| m[i][j]))
}
fn affine(l: Matrix, p: [f64; 3]) -> Mat4 {
    let mut out = ID4;
    for i in 0..3 {
        out[i][..3].copy_from_slice(&l[i]);
        out[i][3] = p[i];
    }
    out
}
pub fn packed(m: Mat4) -> Result<(u32, [f64; 16])> {
    let a = linear(m);
    let magnitude = a.iter().flatten().map(|v| v.abs()).fold(0f64, f64::max);
    let mut r = a.map(|row| row.map(|v| v / magnitude));
    let mut converged = false;
    for _ in 0..64 {
        let inv = transpose(inverse(r)?);
        let next = std::array::from_fn(|i| std::array::from_fn(|j| (r[i][j] + inv[i][j]) / 2.));
        let error = (0..3)
            .flat_map(|i| (0..3).map(move |j| (r[i][j] - next[i][j]).abs()))
            .fold(0f64, f64::max);
        r = next;
        if error < 1e-12 {
            converged = true;
            break;
        }
    }
    if !converged {
        return Err("Transform polar decomposition did not converge".into());
    }
    if determinant(r) < 0. {
        r = r.map(|row| row.map(|v| -v));
    }
    let shear =
        multiply(transpose(r), a).map(|row| row.map(|v| if v.abs() < 1e-14 { 0. } else { v }));
    let trace = r[0][0] + r[1][1] + r[2][2];
    let mut q = [0.; 4];
    if trace > 0. {
        let s = (trace + 1.).max(0.).sqrt() * 2.;
        q = [
            (r[2][1] - r[1][2]) / s,
            (r[0][2] - r[2][0]) / s,
            (r[1][0] - r[0][1]) / s,
            s / 4.,
        ];
    } else {
        let mut i = 0;
        for j in 1..3 {
            if r[j][j] > r[i][i] {
                i = j;
            }
        }
        let j = (i + 1) % 3;
        let k = (i + 2) % 3;
        let s = (1. + r[i][i] - r[j][j] - r[k][k]).max(0.).sqrt() * 2.;
        q[i] = s / 4.;
        q[j] = (r[j][i] + r[i][j]) / s;
        q[k] = (r[k][i] + r[i][k]) / s;
        q[3] = (r[k][j] - r[j][k]) / s;
    }
    let length = sum(q.map(|v| v * v)).sqrt();
    let sign = if q[3] < 0. { -1. } else { 1. };
    q = q.map(|v| sign * v / length);
    let mut values = [0.; 16];
    for i in 0..3 {
        values[i] = narrow(m[i][3])?;
    }
    for i in 0..4 {
        values[3 + i] = narrow(q[i])?;
    }
    for i in 0..3 {
        for j in 0..3 {
            values[7 + i * 3 + j] = narrow(shear[i][j])?;
        }
    }
    inverse(std::array::from_fn(|i| {
        std::array::from_fn(|j| values[7 + i * 3 + j])
    }))?;
    let flags = u32::from(values[..3] != [0.; 3])
        | (u32::from(values[3..7] != [0., 0., 0., 1.]) << 1)
        | (u32::from(values[7..] != [1., 0., 0., 0., 1., 0., 0., 0., 1.]) << 2);
    Ok((flags, values))
}
pub struct Context {
    pub linear: Matrix,
    pub rotation: Matrix,
    pub inverse: Matrix,
    pub translation: [f64; 3],
    pub reflected: bool,
    pub reorder: bool,
    pub handedness: f64,
}
impl Context {
    pub fn new(g: &Graph) -> Result<Self> {
        let art = g.id(g.root, "art_tool")?;
        let c = g.id(g.root, "conversion")?;
        if g.int(art, "pointer_size")? != 64 {
            return Err("GR2 requires 64-bit pointers".into());
        }
        fn basis(g: &Graph, n: usize) -> Result<Matrix> {
            let mut m = [
                three(g.field(n, "right")?)?,
                three(g.field(n, "up")?)?,
                three(g.field(n, "back")?)?,
            ];
            for row in &mut m {
                for v in row {
                    *v = narrow(*v)?;
                }
            }
            for i in 0..3 {
                for j in 0..3 {
                    if (sum((0..3).map(|k| m[i][k] * m[j][k])) - f64::from(i == j)).abs() > 1e-5 {
                        return Err("Coordinate basis requires orthonormal axes".into());
                    }
                }
            }
            Ok(transpose(m))
        }
        let source = basis(g, art)?;
        let target = basis(g, c)?;
        let from = narrow(g.real(art, "units_per_meter")?)?;
        let to = narrow(g.real(c, "target_units_per_meter")?)?;
        if from <= 0. || to <= 0. {
            return Err("Coordinate units must be positive".into());
        }
        let origin = three(g.field(art, "origin")?)?
            .map(narrow)
            .into_iter()
            .collect::<Result<Vec<_>>>()?;
        let reflected = g.boolean(c, "reflect_y")?;
        let state = g.text(c, "state")?;
        if !matches!(state, "authored" | "converted")
            || state == "converted"
                && (reflected || source != target || from != to || origin != [0., 0., 0.])
        {
            return Err("Input conversion state conflicts with pending transforms".into());
        }
        let rotation = if source == target {
            ID
        } else {
            multiply(target, transpose(source))
        };
        let scale = to / from;
        let mut l = rotation;
        for row in &mut l {
            for v in row {
                *v = narrow(*v * scale)?;
            }
        }
        Ok(Self {
            linear: l,
            rotation,
            inverse: inverse(l)?,
            translation: [-origin[0], -origin[1], -origin[2]],
            reflected,
            reorder: determinant(l) < 0.,
            handedness: if determinant(rotation) < 0. { -1. } else { 1. },
        })
    }
    pub fn similarity(&self, m: Mat4) -> Mat4 {
        let mut l = linear(m);
        let mut p = [m[0][3], m[1][3], m[2][3]];
        if self.reflected {
            l = multiply(multiply(MIRROR, l), MIRROR);
            p = vector(MIRROR, p);
        }
        l = multiply(multiply(self.linear, l), self.inverse);
        p = vector(self.linear, p);
        for (component, offset) in p.iter_mut().zip(self.translation) {
            *component += offset;
        }
        affine(l, p)
    }
    pub fn inverse_world(&self, m: Mat4) -> Result<[f64; 16]> {
        let inv = inverse(linear(m))?;
        let p = vector(inv, [m[0][3], m[1][3], m[2][3]]).map(|v| -v);
        let result = self.similarity(affine(inv, p));
        let mut out = [0.; 16];
        for i in 0..4 {
            for j in 0..4 {
                out[i * 4 + j] = narrow(result[j][i])?;
            }
        }
        Ok(out)
    }
    pub fn bounds(&self) -> Result<([f64; 3], [f64; 3])> {
        let mut low = [0.; 3];
        let mut high = [0.; 3];
        for i in 0..3 {
            low[i] =
                narrow(self.translation[i] + sum(self.linear[i].map(|v| (v * -2.).min(v * 2.))))?;
            high[i] =
                narrow(self.translation[i] + sum(self.linear[i].map(|v| (v * -2.).max(v * 2.))))?;
        }
        Ok((low, high))
    }
    pub fn stages(
        &self,
        placement: Mat4,
        reflected: bool,
        normal: bool,
        deltas: bool,
    ) -> Result<Vec<(Matrix, [f64; 3], bool)>> {
        let mut l = linear(placement);
        let mut p = [placement[0][3], placement[1][3], placement[2][3]];
        if reflected {
            l = multiply(multiply(MIRROR, l), MIRROR);
            p = vector(MIRROR, p);
        }
        let mut result = Vec::new();
        if reflected {
            result.push((MIRROR, [0.; 3], false));
        }
        if placement != ID4 {
            result.push((l, p, true));
        }
        result.push((self.linear, self.translation, true));
        for stage in &mut result {
            if normal {
                stage.0 = if deltas {
                    transpose(stage.0)
                } else {
                    transpose(inverse(stage.0)?)
                };
            }
        }
        Ok(result)
    }
    pub fn spatial(
        &self,
        mut v: [f64; 3],
        stages: &[(Matrix, [f64; 3], bool)],
        position: bool,
        deltas: bool,
    ) -> Result<[f64; 3]> {
        for &(m, shift, normalize) in stages {
            v = vector(m, v);
            if position && !deltas {
                for i in 0..3 {
                    v[i] += shift[i];
                }
            } else if !position && normalize {
                let length = v[0].hypot(v[1]).hypot(v[2]);
                if length != 0. {
                    v = v.map(|x| x / length);
                }
            }
            for x in &mut v {
                *x = narrow(*x)?;
            }
        }
        Ok(v)
    }
}
