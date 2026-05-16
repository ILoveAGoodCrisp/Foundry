from __future__ import annotations

from dataclasses import dataclass
import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import bpy


INDENT = "    "

_LISP_TO_CORINTH_OPS = {
    "=": "==",
    "!=": "!=",
    ">": ">",
    "<": "<",
    ">=": ">=",
    "<=": "<=",
    "+": "+",
    "-": "-",
    "*": "*",
    "/": "/",
    "%": "%",
    "and": "and",
    "or": "or",
    "not": "not",
}
_CORINTH_TO_LISP_OPS = {value: key for key, value in _LISP_TO_CORINTH_OPS.items()}
_CORINTH_TO_LISP_OPS["=="] = "="
_OP_PRECEDENCE = {
    "or": 1,
    "and": 2,
    "==": 3,
    "!=": 3,
    ">": 3,
    "<": 3,
    ">=": 3,
    "<=": 3,
    "+": 4,
    "-": 4,
    "*": 5,
    "/": 5,
    "%": 5,
}
_TAG_EXTENSIONS = {
    "animation_graph",
    "biped",
    "bitmap",
    "cinematic",
    "cinematic_scene",
    "cinematic_scene_data",
    "collision_model",
    "crate",
    "damage_effect",
    "decal",
    "device",
    "device_control",
    "device_machine",
    "effect",
    "equipment",
    "garbage",
    "light",
    "material",
    "model",
    "model_animation_graph",
    "physics_model",
    "projectile",
    "render_model",
    "scenario",
    "scenario_structure_bsp",
    "scenery",
    "shader",
    "sound",
    "sound_looping",
    "vehicle",
    "weapon",
}


@dataclass
class _Token:
    kind: str
    value: str


@dataclass
class _Comment:
    text: str
    block: bool = False


@dataclass
class _CAtom:
    value: str


@dataclass
class _CCall:
    name: str
    args: list


@dataclass
class _CBinary:
    op: str
    left: object
    right: object


@dataclass
class _CUnary:
    op: str
    value: object


@dataclass
class _CGlobal:
    var_type: str
    name: str
    value: object


@dataclass
class _CScript:
    script_type: str
    return_type: str
    name: str
    params: list[tuple[str, str]]
    body: list


@dataclass
class _CBegin:
    body: list


@dataclass
class _CIf:
    condition: object
    then_body: list
    elseif_blocks: list[tuple[object, list]]
    else_body: list


@dataclass
class _CRepeat:
    body: list
    condition: object
    args: list


@dataclass
class _CCountBlock:
    kind: str
    count: object
    body: list


@dataclass
class _CAssign:
    target: str
    value: object


@dataclass
class _CExprStatement:
    value: object


def _indent(level: int) -> str:
    return INDENT * level


def _is_comment(value) -> bool:
    return isinstance(value, _Comment)


def _without_comments(values: list) -> list:
    return [value for value in values if not _is_comment(value)]


def _read_quoted(src: str, start: int, quote: str) -> tuple[str, int]:
    i = start + 1
    while i < len(src):
        if src[i] == "\\" and i + 1 < len(src):
            i += 2
            continue
        if src[i] == quote:
            return src[start:i + 1], i + 1
        i += 1
    return src[start:], len(src)


def _tokenize_lisp(src: str) -> list[_Token]:
    tokens = []
    i = 0
    while i < len(src):
        char = src[i]
        if char.isspace():
            i += 1
            continue
        if src.startswith(";*", i):
            end = src.find("*;", i + 2)
            if end == -1:
                tokens.append(_Token("comment_block", src[i + 2:]))
                break
            tokens.append(_Token("comment_block", src[i + 2:end]))
            i = end + 2
            continue
        if char == ";":
            end = src.find("\n", i + 1)
            if end == -1:
                tokens.append(_Token("comment_line", src[i + 1:]))
                break
            tokens.append(_Token("comment_line", src[i + 1:end]))
            i = end
            continue
        if char == '"':
            value, i = _read_quoted(src, i, '"')
            tokens.append(_Token("atom", value))
            continue
        if char in "()":
            tokens.append(_Token(char, char))
            i += 1
            continue

        start = i
        while i < len(src):
            char = src[i]
            if char.isspace() or char in "()":
                break
            if char == ";":
                break
            i += 1
        tokens.append(_Token("atom", src[start:i]))

    return tokens


def _parse_lisp_document(src: str) -> list:
    tokens = _tokenize_lisp(src)
    index = 0

    def parse_expr():
        nonlocal index
        token = tokens[index]
        if token.kind == "comment_line":
            index += 1
            return _Comment(token.value)
        if token.kind == "comment_block":
            index += 1
            return _Comment(token.value, True)
        if token.value == "(":
            index += 1
            values = []
            while index < len(tokens) and tokens[index].value != ")":
                values.append(parse_expr())
            if index < len(tokens) and tokens[index].value == ")":
                index += 1
            return values
        index += 1
        return token.value

    expressions = []
    while index < len(tokens):
        if tokens[index].value == ")":
            index += 1
            continue
        expressions.append(parse_expr())

    return expressions


def _tokenize_corinth(src: str) -> list[_Token]:
    tokens = []
    i = 0
    two_char_ops = {"==", "!=", ">=", "<="}
    one_char_ops = set("=+-*/%<>")
    punctuation = set("(),;")

    while i < len(src):
        char = src[i]
        if char.isspace():
            i += 1
            continue
        if src.startswith("//", i):
            end = src.find("\n", i + 2)
            if end == -1:
                tokens.append(_Token("comment_line", src[i + 2:]))
                break
            tokens.append(_Token("comment_line", src[i + 2:end]))
            i = end
            continue
        if src.startswith("/*", i):
            end = src.find("*/", i + 2)
            if end == -1:
                tokens.append(_Token("comment_block", src[i + 2:]))
                break
            tokens.append(_Token("comment_block", src[i + 2:end]))
            i = end + 2
            continue
        if char in "\"'":
            value, i = _read_quoted(src, i, char)
            tokens.append(_Token("atom", value))
            continue
        if i + 1 < len(src) and src[i:i + 2] in two_char_ops:
            tokens.append(_Token("operator", src[i:i + 2]))
            i += 2
            continue
        if char in one_char_ops:
            tokens.append(_Token("operator", char))
            i += 1
            continue
        if char in punctuation:
            tokens.append(_Token(char, char))
            i += 1
            continue

        start = i
        while i < len(src):
            char = src[i]
            if char.isspace() or char in punctuation or char in one_char_ops:
                break
            if src.startswith("//", i) or src.startswith("/*", i):
                break
            i += 1
        tokens.append(_Token("atom", src[start:i]))

    return tokens


def _token_lower(token: _Token | None) -> str:
    return token.value.lower() if token else ""


class _CorinthParser:
    def __init__(self, src: str):
        self.tokens = _tokenize_corinth(src)
        self.index = 0

    def _peek(self, offset: int = 0) -> _Token | None:
        index = self.index + offset
        if index >= len(self.tokens):
            return None
        return self.tokens[index]

    def _advance(self) -> _Token:
        token = self.tokens[self.index]
        self.index += 1
        return token

    def _match(self, value: str) -> bool:
        token = self._peek()
        if token and token.value == value:
            self.index += 1
            return True
        return False

    def _match_keyword(self, keyword: str) -> bool:
        token = self._peek()
        if token and token.kind == "atom" and token.value.lower() == keyword:
            self.index += 1
            return True
        return False

    def _consume_atom_value(self) -> str:
        token = self._peek()
        if token is None:
            return ""
        return self._advance().value

    def _at_stop(self, stop_values: set[str]) -> bool:
        token = self._peek()
        if token is None:
            return True
        return token.value in stop_values or token.value.lower() in stop_values

    def parse_document(self) -> list:
        statements = []
        while self._peek() is not None:
            statement = self.parse_statement()
            if statement is None:
                self.index += 1
                continue
            statements.append(statement)
        return statements

    def parse_block(self, stop_values: set[str]) -> list:
        statements = []
        while self._peek() is not None and not self._at_stop(stop_values):
            statement = self.parse_statement()
            if statement is None:
                break
            statements.append(statement)
        return statements

    def parse_statement(self):
        token = self._peek()
        if token is None:
            return None
        if token.kind == "comment_line":
            self.index += 1
            return _Comment(token.value)
        if token.kind == "comment_block":
            self.index += 1
            return _Comment(token.value, True)

        keyword = _token_lower(token)
        if keyword in {"end", "else", "elseif", "then", "until"}:
            return None
        if keyword == "global":
            return self.parse_global()
        if keyword == "script":
            return self.parse_script()
        if keyword == "begin":
            return self.parse_begin()
        if keyword == "if":
            return self.parse_if()
        if keyword == "repeat":
            return self.parse_repeat()
        if keyword in {"begin_count", "begin_random_count"}:
            return self.parse_count_block()
        if self._is_assignment_statement():
            return self.parse_assignment()

        value = self.parse_expression({";"})
        self._match(";")
        return _CExprStatement(value)

    def parse_global(self):
        self._match_keyword("global")
        var_type = self._consume_atom_value()
        name = self._consume_atom_value()
        value = _CAtom("")
        if self._match("="):
            value = self.parse_expression({";"})
        self._match(";")
        return _CGlobal(var_type, name, value)

    def parse_script(self):
        self._match_keyword("script")
        script_type = self._consume_atom_value()
        return_type = self._consume_atom_value()
        name = self._consume_atom_value()
        params = []
        if self._match("("):
            while self._peek() is not None and not self._match(")"):
                param_type = self._consume_atom_value()
                if self._peek() is None or self._peek().value == ")":
                    param_name = ""
                else:
                    param_name = self._consume_atom_value()
                if param_type or param_name:
                    params.append((param_type, param_name))
                self._match(",")
        body = self.parse_block({"end"})
        self._match_keyword("end")
        self._match(";")
        return _CScript(script_type, return_type, name, params, body)

    def parse_begin(self):
        self._match_keyword("begin")
        body = self.parse_block({"end"})
        self._match_keyword("end")
        self._match(";")
        return _CBegin(body)

    def parse_if(self):
        self._match_keyword("if")
        condition = self.parse_expression({"then"})
        self._match_keyword("then")
        then_body = self.parse_block({"elseif", "else", "end"})
        elseif_blocks = []
        while self._match_keyword("elseif"):
            elseif_condition = self.parse_expression({"then"})
            self._match_keyword("then")
            elseif_body = self.parse_block({"elseif", "else", "end"})
            elseif_blocks.append((elseif_condition, elseif_body))
        else_body = []
        if self._match_keyword("else"):
            else_body = self.parse_block({"end"})
        self._match_keyword("end")
        self._match(";")
        return _CIf(condition, then_body, elseif_blocks, else_body)

    def parse_repeat(self):
        self._match_keyword("repeat")
        body = self.parse_block({"until"})
        self._match_keyword("until")
        self._match("(")
        condition = self.parse_expression({",", ")"})
        args = []
        while self._match(","):
            args.append(self.parse_expression({",", ")"}))
        self._match(")")
        self._match(";")
        return _CRepeat(body, condition, args)

    def parse_count_block(self):
        kind = self._advance().value
        count = _CAtom("")
        if self._match("("):
            count = self.parse_expression({")"})
            self._match(")")
        body = self.parse_block({"end"})
        self._match_keyword("end")
        self._match(";")
        return _CCountBlock(kind, count, body)

    def parse_assignment(self):
        target = self._consume_atom_value()
        self._match("=")
        value = self.parse_expression({";"})
        self._match(";")
        return _CAssign(target, value)

    def _is_assignment_statement(self) -> bool:
        return (
            self._peek() is not None
            and self._peek().kind == "atom"
            and self._peek(1) is not None
            and self._peek(1).value == "="
        )

    def parse_expression(self, stop_values: set[str] | None = None, min_precedence: int = 0):
        if stop_values is None:
            stop_values = set()
        left = self.parse_unary(stop_values)
        while self._peek() is not None and not self._at_stop(stop_values):
            token = self._peek()
            op = token.value.lower() if token.value.lower() in _OP_PRECEDENCE else token.value
            precedence = _OP_PRECEDENCE.get(op)
            if precedence is None or precedence < min_precedence:
                break
            self._advance()
            right = self.parse_expression(stop_values, precedence + 1)
            left = _CBinary(op, left, right)
        return left

    def parse_unary(self, stop_values: set[str]):
        token = self._peek()
        if token is not None and not self._at_stop(stop_values):
            op = token.value.lower() if token.value.lower() == "not" else token.value
            if op in {"not", "-"}:
                self._advance()
                return _CUnary(op, self.parse_unary(stop_values))
        return self.parse_primary(stop_values)

    def parse_primary(self, stop_values: set[str]):
        token = self._peek()
        if token is None or self._at_stop(stop_values):
            return _CAtom("")
        if self._match("("):
            value = self.parse_expression({")"})
            self._match(")")
            return value

        value = self._advance().value
        expr = _CAtom(value)
        while self._match("("):
            args = []
            if not self._match(")"):
                while self._peek() is not None:
                    args.append(self.parse_expression({",", ")"}))
                    if self._match(")"):
                        break
                    self._match(",")
            if isinstance(expr, _CAtom):
                expr = _CCall(expr.value, args)
            else:
                break
        return expr


def _atom_lisp_to_corinth(atom: str) -> str:
    if not atom or atom.startswith(('"', "'")):
        return atom
    if "/" in atom and "\\" not in atom:
        if "." in atom and atom.rfind(".") > atom.rfind("/"):
            return f"'{atom}'"
        return atom.replace("/", ".")
    return atom


def _atom_corinth_to_lisp(atom: str) -> str:
    if len(atom) > 1 and atom[0] == "'" and atom[-1] == "'":
        return atom[1:-1]
    if "\\" in atom:
        return atom
    if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*\.[A-Za-z_][A-Za-z0-9_]*", atom):
        extension = atom.rsplit(".", 1)[1].lower()
        if extension not in _TAG_EXTENSIONS:
            return atom.replace(".", "/", 1)
    return atom


def _old_head(expr) -> str:
    if not isinstance(expr, list):
        return ""
    parts = _without_comments(expr)
    if not parts or not isinstance(parts[0], str):
        return ""
    return parts[0]


def _old_expr_to_corinth(expr, parent_precedence: int = 0) -> str:
    if _is_comment(expr):
        return ""
    if isinstance(expr, str):
        return _atom_lisp_to_corinth(expr)
    if not isinstance(expr, list):
        return str(expr)

    parts = _without_comments(expr)
    if not parts:
        return ""
    fn = parts[0]
    args = parts[1:]
    if not isinstance(fn, str):
        return _old_expr_to_corinth(fn)

    if fn == "set" and len(args) >= 2:
        return f"{_old_expr_to_corinth(args[0])}={_old_expr_to_corinth(args[1])}"
    if fn in _LISP_TO_CORINTH_OPS:
        return _old_infix_to_corinth(fn, args, parent_precedence)

    return f"{_atom_lisp_to_corinth(fn)}({', '.join(_old_expr_to_corinth(arg) for arg in args)})"


def _old_infix_to_corinth(op: str, args: list, parent_precedence: int = 0) -> str:
    corinth_op = _LISP_TO_CORINTH_OPS[op]
    precedence = _OP_PRECEDENCE.get(corinth_op, 6)
    if not args:
        return ""
    if op == "not":
        result = f"not {_old_expr_to_corinth(args[0], precedence)}"
    elif op == "-" and len(args) == 1:
        result = f"-{_old_expr_to_corinth(args[0], precedence)}"
    else:
        result = f" {corinth_op} ".join(_old_expr_to_corinth(arg, precedence) for arg in args)
    if precedence < parent_precedence:
        return f"({result})"
    return result


def _block_comment_lines(text: str) -> list[str]:
    lines = text.splitlines()
    if lines and lines[0] == "":
        lines = lines[1:]
    if lines and lines[-1] == "":
        lines = lines[:-1]
    return lines


def _comment_to_corinth(comment: _Comment, level: int) -> list[str]:
    ind = _indent(level)
    if not comment.block:
        return [f"{ind}//{comment.text}"]
    lines = _block_comment_lines(comment.text)
    if not lines:
        return [f"{ind}/**/"]
    if len(lines) == 1:
        return [f"{ind}/*{lines[0]}*/"]
    return [f"{ind}/*", *(f"{ind}{line}" for line in lines), f"{ind}*/"]


def _old_statement_to_corinth(expr, level: int = 0) -> list[str]:
    ind = _indent(level)
    if _is_comment(expr):
        return _comment_to_corinth(expr, level)
    if isinstance(expr, str):
        return [f"{ind}{_atom_lisp_to_corinth(expr)};"]
    if not isinstance(expr, list):
        return [f"{ind}{expr};"]

    parts = _without_comments(expr)
    if not parts:
        return []
    fn = parts[0]
    args = parts[1:]
    if not isinstance(fn, str):
        return [f"{ind}{_old_expr_to_corinth(expr)};"]

    if fn == "global":
        return [_old_global_to_corinth(args, level)]
    if fn == "script":
        return _old_script_to_corinth(args, level)
    if fn == "begin":
        return _old_block_to_corinth("begin", args, level)
    if fn == "if":
        return _old_if_to_corinth(args, level)
    if fn == "cond":
        return _old_cond_to_corinth(args, level)
    if fn == "sleep_until":
        return _old_sleep_until_to_corinth(args, level)
    if fn in {"begin_count", "begin_random_count"}:
        return _old_count_block_to_corinth(fn, args, level)

    return [f"{ind}{_old_expr_to_corinth(expr)};"]


def _old_global_to_corinth(args: list, level: int) -> str:
    ind = _indent(level)
    var_type = _old_expr_to_corinth(args[0]) if args else ""
    name = _old_expr_to_corinth(args[1]) if len(args) > 1 else ""
    value = _old_expr_to_corinth(args[2]) if len(args) > 2 else ""
    return f"{ind}global {var_type} {name}={value};"


def _old_script_to_corinth(args: list, level: int) -> list[str]:
    if len(args) < 3:
        return [f"{_indent(level)}{_old_expr_to_corinth(['script', *args])};"]

    script_type = _old_expr_to_corinth(args[0])
    return_type = _old_expr_to_corinth(args[1])
    signature = args[2]
    body = args[3:]
    params = []
    if isinstance(signature, list):
        signature_parts = _without_comments(signature)
        name = _old_expr_to_corinth(signature_parts[0]) if signature_parts else ""
        for param in signature_parts[1:]:
            param_parts = _without_comments(param) if isinstance(param, list) else [param]
            if len(param_parts) >= 2:
                params.append(f"{_old_expr_to_corinth(param_parts[0])} {_old_expr_to_corinth(param_parts[1])}")
    else:
        name = _old_expr_to_corinth(signature)

    lines = [f"{_indent(level)}script {script_type} {return_type} {name}({', '.join(params)})"]
    for statement in body:
        lines.extend(_old_statement_to_corinth(statement, level + 1))
    lines.append(f"{_indent(level)}end")
    return lines


def _old_block_to_corinth(name: str, body: list, level: int) -> list[str]:
    lines = [f"{_indent(level)}{name}"]
    for statement in body:
        lines.extend(_old_statement_to_corinth(statement, level + 1))
    lines.append(f"{_indent(level)}end")
    return lines


def _old_branch_to_corinth(expr, level: int) -> list[str]:
    if isinstance(expr, list) and _old_head(expr) == "begin":
        lines = []
        for statement in _without_comments(expr)[1:]:
            lines.extend(_old_statement_to_corinth(statement, level))
        return lines
    return _old_statement_to_corinth(expr, level)


def _old_if_to_corinth(args: list, level: int) -> list[str]:
    if len(args) < 2:
        return [f"{_indent(level)}if {_old_expr_to_corinth(args[0]) if args else ''} then", f"{_indent(level)}end"]
    lines = [f"{_indent(level)}if {_old_expr_to_corinth(args[0])} then"]
    lines.extend(_old_branch_to_corinth(args[1], level + 1))
    if len(args) > 2:
        lines.append(f"{_indent(level)}else")
        lines.extend(_old_branch_to_corinth(args[2], level + 1))
    lines.append(f"{_indent(level)}end")
    return lines


def _old_cond_to_corinth(args: list, level: int) -> list[str]:
    lines = []
    opened_if = False
    for clause in args:
        if not isinstance(clause, list):
            continue
        clause_parts = _without_comments(clause)
        if not clause_parts:
            continue
        condition = clause_parts[0]
        body = clause_parts[1:]
        condition_text = _old_expr_to_corinth(condition)
        is_else = isinstance(condition, str) and condition.lower() in {"else", "true"}
        if is_else:
            lines.append(f"{_indent(level)}else")
        else:
            keyword = "if" if not opened_if else "elseif"
            lines.append(f"{_indent(level)}{keyword} {condition_text} then")
            opened_if = True
        for statement in body:
            lines.extend(_old_statement_to_corinth(statement, level + 1))
    if opened_if:
        lines.append(f"{_indent(level)}end")
    return lines


def _old_sleep_until_to_corinth(args: list, level: int) -> list[str]:
    ind = _indent(level)
    if args and isinstance(args[0], list) and _old_head(args[0]) == "begin":
        begin_parts = _without_comments(args[0])[1:]
        if begin_parts:
            condition = begin_parts[-1]
            body = begin_parts[:-1]
            until_args = [_old_expr_to_corinth(condition), *(_old_expr_to_corinth(arg) for arg in args[1:])]
            lines = [f"{ind}repeat"]
            for statement in body:
                lines.extend(_old_statement_to_corinth(statement, level + 1))
            lines.append(f"{ind}until({', '.join(until_args)});")
            return lines
    return [f"{ind}sleep_until({', '.join(_old_expr_to_corinth(arg) for arg in args)});"]


def _old_count_block_to_corinth(kind: str, args: list, level: int) -> list[str]:
    if not args:
        return [f"{_indent(level)}{kind}()", f"{_indent(level)}end"]
    lines = [f"{_indent(level)}{kind}({_old_expr_to_corinth(args[0])})"]
    for statement in args[1:]:
        lines.extend(_old_statement_to_corinth(statement, level + 1))
    lines.append(f"{_indent(level)}end")
    return lines


def _lisp_document_to_corinth(src: str) -> str:
    expressions = _parse_lisp_document(src)
    meaningful = [expr for expr in expressions if not _is_comment(expr)]
    if expressions and not meaningful:
        lines = []
        for expr in expressions:
            lines.extend(_old_statement_to_corinth(expr))
        return "\n".join(lines)
    if meaningful and all(isinstance(expr, list) for expr in meaningful):
        lines = []
        for expr in expressions:
            lines.extend(_old_statement_to_corinth(expr))
        return "\n".join(lines)
    return _lisp_lines_to_corinth(src)


def _lisp_lines_to_corinth(src: str) -> str:
    output = []
    for line in src.splitlines():
        stripped = line.strip()
        indent = line[:len(line) - len(line.lstrip())]
        if not stripped:
            output.append(line)
            continue
        if _looks_corinth_like(stripped):
            output.append(line)
            continue

        expressions = _parse_lisp_document(stripped)
        meaningful = [expr for expr in expressions if not _is_comment(expr)]
        if not meaningful:
            for expr in expressions:
                if _is_comment(expr):
                    output.extend(indent + converted_line for converted_line in _comment_to_corinth(expr, 0))
            continue
        if len(meaningful) == 1 and isinstance(meaningful[0], list):
            lines = _old_statement_to_corinth(meaningful[0])
        elif len(meaningful) == 1:
            lines = _old_statement_to_corinth(meaningful[0])
        else:
            statement = [meaningful[0], *meaningful[1:]]
            lines = _old_statement_to_corinth(statement)
        output.extend(indent + converted_line for converted_line in lines)
    return "\n".join(output)


def _comment_to_lisp(comment: _Comment, level: int) -> list[str]:
    ind = _indent(level)
    if not comment.block:
        return [f"{ind};{comment.text}"]
    lines = _block_comment_lines(comment.text)
    if not lines:
        return [f"{ind};**;"]
    if len(lines) == 1:
        return [f"{ind};*{lines[0]}*;"]
    return [f"{ind};*", *(f"{ind}{line}" for line in lines), f"{ind}*;"]


def _corinth_expr_to_lisp(expr) -> str:
    if isinstance(expr, _CAtom):
        return _atom_corinth_to_lisp(expr.value)
    if isinstance(expr, _CCall):
        args = " ".join(_corinth_expr_to_lisp(arg) for arg in expr.args)
        return f"({_atom_corinth_to_lisp(expr.name)}{(' ' + args) if args else ''})"
    if isinstance(expr, _CBinary):
        op = _CORINTH_TO_LISP_OPS.get(expr.op, expr.op)
        return f"({op} {_corinth_expr_to_lisp(expr.left)} {_corinth_expr_to_lisp(expr.right)})"
    if isinstance(expr, _CUnary):
        return f"({expr.op} {_corinth_expr_to_lisp(expr.value)})"
    return str(expr)


def _corinth_statement_to_lisp(statement, level: int = 0) -> list[str]:
    ind = _indent(level)
    if _is_comment(statement):
        return _comment_to_lisp(statement, level)
    if isinstance(statement, _CGlobal):
        return [f"{ind}(global {statement.var_type} {statement.name} {_corinth_expr_to_lisp(statement.value)})"]
    if isinstance(statement, _CScript):
        return _corinth_script_to_lisp(statement, level)
    if isinstance(statement, _CBegin):
        return _corinth_named_block_to_lisp("begin", statement.body, level)
    if isinstance(statement, _CIf):
        return _corinth_if_to_lisp(statement, level)
    if isinstance(statement, _CRepeat):
        return _corinth_repeat_to_lisp(statement, level)
    if isinstance(statement, _CCountBlock):
        return _corinth_count_block_to_lisp(statement, level)
    if isinstance(statement, _CAssign):
        return [f"{ind}(set {_atom_corinth_to_lisp(statement.target)} {_corinth_expr_to_lisp(statement.value)})"]
    if isinstance(statement, _CExprStatement):
        return [f"{ind}{_corinth_expr_to_lisp(statement.value)}"]
    return [f"{ind}{statement}"]


def _corinth_script_to_lisp(statement: _CScript, level: int) -> list[str]:
    ind = _indent(level)
    if statement.params:
        params = " ".join(f"({param_type} {param_name})" for param_type, param_name in statement.params)
        header = f"{ind}(script {statement.script_type} {statement.return_type} ({statement.name} {params})"
    else:
        header = f"{ind}(script {statement.script_type} {statement.return_type} {statement.name}"
    lines = [header]
    for body_statement in statement.body:
        lines.extend(_corinth_statement_to_lisp(body_statement, level + 1))
    lines.append(f"{ind})")
    return lines


def _corinth_named_block_to_lisp(name: str, body: list, level: int) -> list[str]:
    lines = [f"{_indent(level)}({name}"]
    for statement in body:
        lines.extend(_corinth_statement_to_lisp(statement, level + 1))
    lines.append(f"{_indent(level)})")
    return lines


def _corinth_body_as_lisp_expr(body: list, level: int) -> list[str]:
    meaningful = [statement for statement in body if not _is_comment(statement)]
    if len(meaningful) == 1 and len(body) == 1:
        return _corinth_statement_to_lisp(meaningful[0], level)
    return _corinth_named_block_to_lisp("begin", body, level)


def _corinth_if_to_lisp(statement: _CIf, level: int) -> list[str]:
    ind = _indent(level)
    if statement.elseif_blocks:
        lines = [f"{ind}(cond"]
        clauses = [(statement.condition, statement.then_body), *statement.elseif_blocks]
        for condition, body in clauses:
            lines.append(f"{_indent(level + 1)}({_corinth_expr_to_lisp(condition)}")
            lines.extend(_corinth_body_as_lisp_expr(body, level + 2))
            lines.append(f"{_indent(level + 1)})")
        if statement.else_body:
            lines.append(f"{_indent(level + 1)}(true")
            lines.extend(_corinth_body_as_lisp_expr(statement.else_body, level + 2))
            lines.append(f"{_indent(level + 1)})")
        lines.append(f"{ind})")
        return lines

    lines = [f"{ind}(if {_corinth_expr_to_lisp(statement.condition)}"]
    lines.extend(_corinth_body_as_lisp_expr(statement.then_body, level + 1))
    if statement.else_body:
        lines.extend(_corinth_body_as_lisp_expr(statement.else_body, level + 1))
    lines.append(f"{ind})")
    return lines


def _corinth_repeat_to_lisp(statement: _CRepeat, level: int) -> list[str]:
    ind = _indent(level)
    lines = [f"{ind}(sleep_until", f"{_indent(level + 1)}(begin"]
    for body_statement in statement.body:
        lines.extend(_corinth_statement_to_lisp(body_statement, level + 2))
    lines.append(f"{_indent(level + 2)}{_corinth_expr_to_lisp(statement.condition)}")
    lines.append(f"{_indent(level + 1)})")
    for arg in statement.args:
        lines.append(f"{_indent(level + 1)}{_corinth_expr_to_lisp(arg)}")
    lines.append(f"{ind})")
    return lines


def _corinth_count_block_to_lisp(statement: _CCountBlock, level: int) -> list[str]:
    lines = [f"{_indent(level)}({statement.kind}", f"{_indent(level + 1)}{_corinth_expr_to_lisp(statement.count)}"]
    for body_statement in statement.body:
        lines.extend(_corinth_statement_to_lisp(body_statement, level + 1))
    lines.append(f"{_indent(level)})")
    return lines


def _corinth_document_to_lisp(src: str) -> str:
    parser = _CorinthParser(src)
    statements = parser.parse_document()
    lines = []
    for statement in statements:
        lines.extend(_corinth_statement_to_lisp(statement))
    return "\n".join(lines)


def _looks_corinth_like(src: str) -> bool:
    stripped = src.strip()
    if not stripped:
        return False
    if stripped.startswith(("//", "/*")):
        return True
    if stripped.endswith(";"):
        return True
    if stripped in {"end", "else"}:
        return True
    if stripped.startswith(("script ", "global ", "if ", "elseif ", "repeat", "begin_count(", "begin_random_count(")):
        return True
    fn_end = stripped.find("(")
    space = stripped.find(" ")
    return fn_end > 0 and (space == -1 or fn_end < space)


def _looks_lisp_like(src: str) -> bool:
    stripped = src.strip()
    if not stripped:
        return False
    if stripped.startswith(("(", ";")):
        return True
    if not _looks_corinth_like(stripped) and " " in stripped:
        return True
    return False


def _looks_corinth_document(src: str) -> bool:
    for line in src.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if _looks_corinth_like(stripped):
            return True
        if re.search(r"\w\s*(==|!=|>=|<=|=|\+|\*|%)\s*\w", stripped):
            return True
    return False


def lisp_to_corinth(src: str) -> str:
    if not src.strip():
        return ""
    return _lisp_document_to_corinth(src)


def corinth_to_lisp(src: str) -> str:
    if not src.strip():
        return ""
    if _looks_lisp_like(src) and not _looks_corinth_document(src):
        return src
    return _corinth_document_to_lisp(src)


def convert(src: str, corinth: bool) -> str:
    if corinth:
        if _looks_corinth_document(src) and not _looks_lisp_like(src):
            return src
        return lisp_to_corinth(src)
    return corinth_to_lisp(src)


def script_from_text(corinth: bool, raw_text: str = "", text_file: bpy.types.Text = None, use_text_file: bool | None = None):
    """Returns valid halo script from raw text, or the optional text file."""

    if use_text_file is None:
        use_text_file = text_file is not None

    if use_text_file:
        if text_file is None:
            return ""
        return convert(text_file.as_string(), corinth)

    if raw_text.strip():
        return convert(raw_text, corinth)

    return ""
