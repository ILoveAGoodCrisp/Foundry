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
    try:
        while len(closed) < 2:
            source, data = messages.get()
            if data is None:
                closed.add(source)
                continue
            sink = sinks[source]
            if sink != subprocess.DEVNULL:
                if sink is None:
                    sink = sys.stdout if source == 0 else sys.stderr
                if hasattr(sink, 'buffer'):
                    sink.buffer.write(data)
                elif isinstance(sink, io.TextIOBase):
                    sink.write(data.decode(errors='replace'))
                else:
                    sink.write(data)
                sink.flush()
            tails[source] = (tails[source] + data)[-8192:]
            error = shader_prompt_error(tails[source])
            if error:
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
