from pathlib import Path

from mathutils import Quaternion, Vector

def gen_lines(filepath: Path | str):
    with open(filepath, "r") as file:
        for line in file:
            yield line.partition(";")[0].strip()
            
def sint(x):
    return int(float(x))

def to_vector(line):
    numbers = line.split()
    return Vector(([float(n) for n in numbers]))

def to_quaternion(line):
    numbers = line.split()
    assert len(numbers) == 4
    w, x, y, z = float(numbers[3]), float(numbers[0]), float(numbers[1]), float(numbers[2])
    return Quaternion((w, x, y, z))