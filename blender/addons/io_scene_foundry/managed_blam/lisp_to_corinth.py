import re

TOKEN_RE = re.compile(
    r'"[^"]*"|\(|\)|[^\s()]+'
)

def _tokenize(src: str) -> list[str]:
    return TOKEN_RE.findall(src)


def _parse_expr(tokens: list[str]) -> str:
    token = tokens.pop(0)

    if token == "(":
        fn = tokens.pop(0)
        args = []

        while tokens and tokens[0] != ")":
            args.append(_parse_expr(tokens))

        tokens.pop(0)
        return f"{fn}({', '.join(args)})"

    return token


def _lisp_to_c(src: str) -> str:
    tokens = _tokenize(src)
    if not tokens:
        return ""

    fn = tokens.pop(0)
    args = []

    while tokens:
        args.append(_parse_expr(tokens))

    return f"{fn}({', '.join(args)});"

def _looks_c_like(src: str) -> bool:
    src = src.strip()
    if src.endswith(";"):
        return True
    if "(" in src:
        fn_end = src.find("(")
        space = src.find(" ")
        if space == -1 or fn_end < space:
            return True
    return False


def _is_atomic(src: str) -> bool:
    return (
        "(" not in src
        and ")" not in src
        and " " not in src
    )

def convert(src: str) -> str:
    output = []

    for line in src.splitlines():
        stripped = line.strip()
        indent = line[:len(line) - len(line.lstrip())]

        if not stripped:
            output.append(line)
            continue

        if stripped == ")":
            output.append(line)
            continue

        if _looks_c_like(stripped):
            output.append(line)
            continue

        if _is_atomic(stripped):
            output.append(indent + stripped + ";")
            continue
        
        output.append(indent + _lisp_to_c(stripped))

    return "\n".join(output)
