"""Run openfortivpn and keep its process, PTY and temporary config in sync."""

import os
import pty
import select
import signal
import stat
import subprocess
import tempfile
import termios
import threading
from enum import Enum
from typing import Optional

import gi
gi.require_version('Gtk', '4.0')
from gi.repository import GLib, GObject

from openfortivpn_gtk.profile import VPNProfile


class VPNState(Enum):
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    DISCONNECTING = "disconnecting"
    ERROR = "error"


class VPNManager(GObject.Object):
    """Manage one connection at a time; UI state is changed on the GTK thread."""

    __gsignals__ = {
        'state-changed': (GObject.SignalFlags.RUN_FIRST, None, (str,)),
        'log-message': (GObject.SignalFlags.RUN_FIRST, None, (str,)),
        'error': (GObject.SignalFlags.RUN_FIRST, None, (str,)),
        'otp-required': (GObject.SignalFlags.RUN_FIRST, None, ()),
        'password-required': (GObject.SignalFlags.RUN_FIRST, None, ()),
    }

    def __init__(self):
        super().__init__()
        self._process: Optional[subprocess.Popen] = None
        self._master_fd: Optional[int] = None
        self._state = VPNState.DISCONNECTED
        self._current_profile: Optional[VPNProfile] = None
        self._read_thread: Optional[threading.Thread] = None

    @property
    def state(self) -> VPNState:
        return self._state

    @property
    def current_profile(self) -> Optional[VPNProfile]:
        return self._current_profile

    @property
    def is_connected(self) -> bool:
        return self._state == VPNState.CONNECTED

    def _set_state(self, state: VPNState):
        self._state = state
        self.emit('state-changed', state.value)

    def _log(self, message: str):
        GLib.idle_add(self.emit, 'log-message', message)

    def _error(self, message: str):
        GLib.idle_add(self.emit, 'error', message)

    @staticmethod
    def _find_system_executable(name: str) -> Optional[str]:
        """Only launch privileged programs from root-owned system locations."""
        system_owner = os.stat('/usr').st_uid
        for directory in ('/usr/bin', '/usr/local/bin', '/usr/sbin', '/bin', '/sbin'):
            path = os.path.join(directory, name)
            resolved = os.path.realpath(path)
            if os.path.dirname(resolved) not in (
                    '/usr/bin', '/usr/local/bin', '/usr/sbin', '/bin', '/sbin'):
                continue
            try:
                file_stat = os.stat(resolved)
                dir_stat = os.stat(os.path.dirname(resolved))
            except OSError:
                continue
            if (stat.S_ISREG(file_stat.st_mode) and file_stat.st_uid == system_owner
                    and not file_stat.st_mode & 0o022 and file_stat.st_mode & 0o111
                    and dir_stat.st_uid == system_owner and not dir_stat.st_mode & 0o022):
                return resolved
        return None

    def _connected(self, process):
        if self._process is process and self._state == VPNState.CONNECTING:
            self._set_state(VPNState.CONNECTED)
        return GLib.SOURCE_REMOVE

    def _finished(self, process, return_code):
        if self._process is not process:
            return GLib.SOURCE_REMOVE
        self._process = None
        self._master_fd = None
        self._read_thread = None
        self._log(f"Processo terminou com código: {return_code}")
        if self._state == VPNState.DISCONNECTING or return_code == 0:
            self._current_profile = None
            self._set_state(VPNState.DISCONNECTED)
        else:
            self._set_state(VPNState.ERROR)
            self._error("A conexão VPN terminou inesperadamente")
        return GLib.SOURCE_REMOVE

    def _read_output(self, process, master_fd, config_file):
        """Drain the PTY, reap the child and remove the secret config."""
        buffer = ""
        otp_prompted = False
        password_prompted = False
        try:
            while True:
                ready, _, _ = select.select([master_fd], [], [], 0.2)
                if ready:
                    try:
                        chunk = os.read(master_fd, 4096)
                    except OSError:  # PTY returns EIO after the child closes it.
                        break
                    if not chunk:
                        break
                    buffer += chunk.decode('utf-8', errors='replace')
                    while '\n' in buffer:
                        line, buffer = buffer.split('\n', 1)
                        line = line.strip()
                        if line:
                            self._log(line)
                        if 'Tunnel is up and running' in line:
                            GLib.idle_add(self._connected, process)
                        if 'authentication' in line.lower() and 'error' in line.lower():
                            self._error("Falha na autenticação")
                    prompt = buffer.lower()
                    if not otp_prompted and any(p in prompt for p in
                            ('one-time password', 'two-factor authentication',
                             'enter otp', 'otp:', 'challenge:')):
                        otp_prompted = True
                        GLib.idle_add(self.emit, 'otp-required')
                    if not password_prompted and 'password:' in prompt and not any(
                            p in prompt for p in ('one-time password', 'otp password')):
                        password_prompted = True
                        GLib.idle_add(self.emit, 'password-required')
                elif process.poll() is not None:
                    break
            if buffer.strip():
                self._log(buffer.strip())
        except Exception as exc:
            self._log(f"Erro ao ler saída: {exc}")
        finally:
            return_code = process.wait()
            try:
                os.close(master_fd)
            except OSError:
                pass
            try:
                os.unlink(config_file)
            except OSError as exc:
                self._log(f"Não foi possível remover configuração temporária: {exc}")
            GLib.idle_add(self._finished, process, return_code)

    def connect_vpn(self, profile: VPNProfile) -> bool:
        if self._process is not None or self._state == VPNState.DISCONNECTING:
            self._error("Aguarde a conexão atual terminar")
            return False

        executable = self._find_system_executable('openfortivpn')
        privilege_tool = self._find_system_executable('pkexec')
        session_tool = self._find_system_executable('setsid')
        if not executable or not privilege_tool or not session_tool:
            self._error("Instale openfortivpn, pkexec e setsid para conectar")
            return False

        try:
            config = profile.to_config_file_content()
        except ValueError as exc:
            self._error(str(exc))
            return False

        config_file = None
        master_fd = slave_fd = None
        try:
            fd, config_file = tempfile.mkstemp(prefix='openfortivpn-', suffix='.conf')
            with os.fdopen(fd, 'w', encoding='utf-8') as file:
                file.write(config)
            master_fd, slave_fd = pty.openpty()
            terminal = termios.tcgetattr(slave_fd)
            terminal[3] &= ~termios.ECHO
            termios.tcsetattr(slave_fd, termios.TCSANOW, terminal)
            process = subprocess.Popen(
                [session_tool, '-c', privilege_tool, executable, '-c', config_file],
                stdin=slave_fd, stdout=slave_fd, stderr=slave_fd,
                close_fds=True,
            )
        except (OSError, subprocess.SubprocessError) as exc:
            self._error(f"Não foi possível iniciar a VPN: {exc}")
            if master_fd is not None:
                os.close(master_fd)
            if config_file is not None:
                os.unlink(config_file)
            return False
        finally:
            if slave_fd is not None:
                os.close(slave_fd)

        self._process = process
        self._master_fd = master_fd
        self._current_profile = profile
        self._set_state(VPNState.CONNECTING)
        self._log(f"Conectando a {profile.name} ({profile.host})...")
        self._read_thread = threading.Thread(
            target=self._read_output, args=(process, master_fd, config_file),
            daemon=True,
        )
        self._read_thread.start()
        return True

    def _stop_process(self, process, master_fd):
        # The PTY is the controlling terminal. Its interrupt character reaches
        # the foreground VPN process even when pkexec made it root-owned.
        try:
            os.write(master_fd, b'\x03')
        except OSError:
            pass
        try:
            process.wait(timeout=3)
            return
        except subprocess.TimeoutExpired:
            pass
        try:
            os.killpg(process.pid, signal.SIGTERM)
        except ProcessLookupError:
            return
        except PermissionError:
            try:
                process.terminate()
            except PermissionError:
                self._error("Não foi possível encerrar a VPN; verifique o processo privilegiado")
                return
        try:
            process.wait(timeout=2)
        except subprocess.TimeoutExpired:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except (ProcessLookupError, PermissionError):
                try:
                    process.kill()
                except (ProcessLookupError, PermissionError):
                    self._error("Não foi possível encerrar a VPN; verifique o processo privilegiado")
                    return
            try:
                process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                self._error("A VPN não respondeu ao pedido de desconexão")

    def disconnect(self, wait: bool = False):
        if self._process is None:
            return
        process = self._process
        master_fd = self._master_fd
        if self._state == VPNState.DISCONNECTING:
            if wait:
                self._stop_process(process, master_fd)
                if self._read_thread:
                    self._read_thread.join(timeout=2)
            return
        self._set_state(VPNState.DISCONNECTING)
        self._log("Desconectando...")
        if wait:
            self._stop_process(process, master_fd)
            if self._read_thread:
                self._read_thread.join(timeout=2)
        else:
            threading.Thread(target=self._stop_process, args=(process, master_fd), daemon=True).start()

    def send_input(self, value: str):
        if self._master_fd is not None and self._process is not None:
            try:
                os.write(self._master_fd, (value + '\n').encode('utf-8'))
            except OSError as exc:
                self._error(f"Não foi possível enviar o código: {exc}")
