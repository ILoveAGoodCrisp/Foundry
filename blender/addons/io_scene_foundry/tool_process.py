"""Monitor Tool without waiting for newline-terminated interactive prompts."""
import io
import os
from concurrent.futures import Future, TimeoutError
import queue
import re
import subprocess
import sys
import threading

from .exceptions import ExportCancelled


SHADER_PROMPT = re.compile(rb"choose\s+a\s+type\s+for\s+the\s+shader\s+['\"]([^'\"\r\n]+)['\"]", re.I)
TOOL_PERCENT_PROGRESS = re.compile(
    rb"^\s*(?!(?:###|-ERROR-|-FATAL-|WARNING\b|WARN\b|ERROR\b|FATAL\b|CRITICAL\b|MESSAGE\b))"
    rb".+?\.{2,}\s*\d+(?:\.\d+)?%\s*[-|/\\]?\s*$", re.I)
TOOL_ROUTINE_PROGRESS = re.compile(
    rb"^\s*(?:section\s+#\d+:\s*)?"
    rb"(?:building|assigning|processing|sorting|pre-sorting|remapping|cleaning|"
    rb"merging|finding|splitting|moving|creating initial planes|coloring leaves|"
    rb"discarding subclusters|reapplying geometry classifications|copying|welding|"
    rb"setting up|reassigning|marking seam sealers|analyzing edges|gridding planes)\b"
    rb"[^'\"\\\r\n]*\.{3,}\s*[-|/\\]?\s*$", re.I)
TOOL_SHADER_SEARCH_PROGRESS = re.compile(
    rb"^\s*looking for shaders in collection (?P<quote>['\"])[^'\"]*(?P=quote)"
    rb"\s+\([^\r\n)]*\)\.{3,}\s*[-|/\\]?\s*$", re.I)
TOOL_DIAGNOSTIC_TEXT = re.compile(
    rb"\b(?:warn(?:ing)?|errors?|fail(?:ed|ure)?|fatal|critical|assert(?:ion)?|"
    rb"exception|invalid|missing|unable|cannot|can't|couldn't|corrupt(?:ed)?|"
    rb"degenerate|not found)\b", re.I)
TOOL_ANSI_ESCAPE = re.compile(rb"\x1b(?:\[[0-?]*[ -/]*[@-~]|\][^\x07]*(?:\x07|\x1b\\))")


class ToolOutputNormalizer:
    """Keep Tool messages while allowing routine progress to update in place."""

    def __init__(self):
        self.pending_carriage_return = False
        self.current_line = b''
        self.progress_pending = False

    @staticmethod
    def visible_text(line):
        line = TOOL_ANSI_ESCAPE.sub(b'', line)
        if b'\b' in line:
            visible = bytearray()
            for character in line:
                if character == 8:
                    if visible:
                        visible.pop()
                else:
                    visible.append(character)
            line = bytes(visible)
        return line

    @classmethod
    def is_progress(cls, line):
        text = cls.visible_text(line)
        if TOOL_DIAGNOSTIC_TEXT.search(text):
            return False
        return bool(TOOL_PERCENT_PROGRESS.match(text) or TOOL_ROUTINE_PROGRESS.match(text)
                    or TOOL_SHADER_SEARCH_PROGRESS.match(text))

    def feed(self, data):
        if not data:
            return data
        output = []
        for part in re.split(rb'([\r\n])', data):
            if not part:
                continue
            if part in (b'\r', b'\n'):
                if part == b'\n' and self.pending_carriage_return:
                    self.pending_carriage_return = False
                    continue
                self.pending_carriage_return = part == b'\r'
                if self.visible_text(self.current_line).strip():
                    self.progress_pending = self.is_progress(self.current_line)
                    output.append(self.current_line + (b'\r' if self.progress_pending else b'\n'))
                self.current_line = b''
            else:
                self.pending_carriage_return = False
                self.current_line += part
        return b''.join(output)

    def finish(self):
        """Commit the final live tracker or unterminated message when Tool exits."""
        if self.visible_text(self.current_line).strip():
            ending = self.current_line + b'\n'
        else:
            ending = b'\n' if self.progress_pending else b''
        self.current_line = b''
        self.pending_carriage_return = False
        self.progress_pending = False
        return ending


def shader_prompt_error(output):
    match = SHADER_PROMPT.search(output)
    if match:
        name = match[1].decode(errors='replace')
        return ExportCancelled(
            f"Tool requested creation of shader '{name}'. Export stopped: "
            "the exported material has no shader tag Tool can resolve. "
            "Check its shader path and exported material name.")


def check_tool_process(launch, command, cwd, stdout=None, stderr=None,
                       tool_patches=None, stdin=None):
    """Forward both streams while aborting on Tool's shader creation menu."""
    process = launch(command, cwd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                     tool_patches=tool_patches, stdin=stdin)
    return monitor_tool_process(process, command, stdout, stderr)


def monitor_tool_process(process, command, stdout=None, stderr=None):
    messages = queue.Queue()

    def read(source, pipe):
        try:
            while data := os.read(pipe.fileno(), 4096):
                messages.put((source, data))
        finally:
            messages.put((source, None))

    pipes = (process.stdout, process.stderr)
    readers = [threading.Thread(target=read, args=(index, pipe), daemon=True)
               for index, pipe in enumerate(pipes)]
    for reader in readers:
        reader.start()
    tails = [b'', b'']
    closed = set()
    sinks = (stdout, stdout if stderr == subprocess.STDOUT else stderr)
    normalizers = [ToolOutputNormalizer(), ToolOutputNormalizer()]
    pending = [b'', b'']

    def write(source, data):
        sink = sinks[source]
        if not data or sink == subprocess.DEVNULL:
            return
        if sink is None:
            sink = sys.stdout if source == 0 else sys.stderr
        if hasattr(sink, 'buffer'):
            sink.buffer.write(data)
        elif isinstance(sink, io.TextIOBase):
            sink.write(data.decode(errors='replace'))
        else:
            sink.write(data)
        sink.flush()

    def forward(source, data):
        # A progress update on the other pipe must not replace a diagnostic
        # that has only partially arrived. Forward complete records together.
        pending[source] += data
        records = re.split(rb'(?<=[\r\n])', pending[source])
        pending[source] = records.pop()
        for record in records:
            write(source, record)

    try:
        while len(closed) < 2:
            source, data = messages.get()
            if data is None:
                forward(source, normalizers[source].finish())
                closed.add(source)
                continue
            forward(source, normalizers[source].feed(data))
            tails[source] = (tails[source] + data)[-8192:]
            error = shader_prompt_error(tails[source])
            if error:
                forward(source, normalizers[source].finish())
                raise error
        returncode = process.wait()
        if returncode:
            raise subprocess.CalledProcessError(returncode, command)
        return 0
    finally:
        if process.poll() is None:
            process.kill()
        process.wait()
        for reader in readers:
            reader.join(timeout=5)
        for pipe in pipes:
            pipe.close()


class MonitoredToolProcess:
    """Background Popen interface that propagates prompt errors on poll/wait."""
    def __init__(self, launch, command, cwd, stdout=None, stderr=None, tool_patches=None):
        self._result = Future()
        self._process = launch(command, cwd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                               stdin=subprocess.DEVNULL, tool_patches=tool_patches)
        owned = []

        def retain(sink):
            if sink is not None and sink not in (subprocess.DEVNULL, subprocess.STDOUT):
                # Callers may close log files as soon as the process starts.
                sink = os.fdopen(os.dup(sink.fileno()), 'wb', buffering=0)
                owned.append(sink)
            return sink

        stdout, stderr = retain(stdout), retain(stderr)

        def run():
            result = None
            failure = None
            try:
                result = monitor_tool_process(self._process, command, stdout, stderr)
            except BaseException as error:
                failure = error
            finally:
                for sink in owned:
                    sink.close()
            if failure is not None:
                self._result.set_exception(failure)
            else:
                self._result.set_result(result)

        threading.Thread(target=run, daemon=True).start()

    def __getattr__(self, name):
        return getattr(self._process, name)

    def poll(self):
        return self._result.result() if self._result.done() else None

    def wait(self, timeout=None):
        try:
            return self._result.result(timeout)
        except TimeoutError:
            raise subprocess.TimeoutExpired(getattr(self._process, 'args', 'Tool'), timeout) from None
