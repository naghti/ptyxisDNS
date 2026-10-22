#!/usr/bin/env python3
"""Window-local HTTP proxy. TLS is tunneled unchanged; no credentials logged."""
import argparse
import os
import select
import signal
import shutil
from pathlib import Path
import socket
import socketserver
import subprocess
import threading


class Handler(socketserver.StreamRequestHandler):
    def handle(self):
        remote = None
        try:
            line = self.rfile.readline(8193)
            if len(line) > 8192:
                return
            method, target, version = line.decode('ascii').strip().split()
            headers = []
            for _ in range(100):
                header = self.rfile.readline(8193)
                if header in (b'\r\n', b'\n', b''):
                    break
                if len(header) > 8192:
                    return
                headers.append(header)
            else:
                return
            if method == 'CONNECT':
                host, port = target.rsplit(':', 1)
                host = host.strip('[]')
                port = int(port)
                prefix = None
            else:
                from urllib.parse import urlsplit
                url = urlsplit(target)
                if url.scheme != 'http' or not url.hostname:
                    raise ValueError('Expected HTTP URL')
                host, port = url.hostname, url.port or 80
                path = (url.path or '/') + (('?' + url.query) if url.query else '')
                headers = [h for h in headers if h.split(b':', 1)[0].lower() not in
                           (b'proxy-connection', b'proxy-authorization', b'connection')]
                prefix = f'{method} {path} {version}\r\n'.encode() + b''.join(headers) + b'Connection: close\r\n\r\n'
            for family, kind, proto, _, address in socket.getaddrinfo(host, port, socket.AF_UNSPEC, socket.SOCK_STREAM):
                attempt = socket.socket(family, kind, proto)
                try:
                    if self.server.interface:
                        attempt.setsockopt(socket.SOL_SOCKET, socket.SO_BINDTODEVICE,
                                           self.server.interface.encode() + b'\0')
                    attempt.settimeout(8)
                    attempt.connect(address)
                    remote = attempt
                    break
                except OSError:
                    attempt.close()
            if remote is None:
                raise OSError('Connection failed')
            if prefix is None:
                self.wfile.write(b'HTTP/1.1 200 Connection Established\r\n\r\n')
                self.wfile.flush()
            else:
                remote.sendall(prefix)
            remote.settimeout(None)
            # rbufsize=0 prevents consuming request bodies/TLS bytes into a file buffer.
            while True:
                ready, _, _ = select.select([remote, self.connection], [], [], 300)
                if not ready:
                    break
                for source in ready:
                    chunk = source.recv(65536)
                    if not chunk:
                        return
                    (self.connection if source is remote else remote).sendall(chunk)
        except (OSError, ValueError, UnicodeError):
            if remote is None:
                try:
                    self.wfile.write(b'HTTP/1.1 502 Bad Gateway\r\nContent-Length: 0\r\n\r\n')
                except OSError:
                    pass
        finally:
            if remote:
                remote.close()

    rbufsize = 0


class Server(socketserver.ThreadingTCPServer):
    daemon_threads = True


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--interface')
    parser.add_argument('command', nargs=argparse.REMAINDER)
    args = parser.parse_args()
    command = args.command
    if command[:1] == ['--']:
        command = command[1:]
    if not command:
        parser.error('Missing command')
    if args.interface:
        socket.if_nametoindex(args.interface)
    with Server(('127.0.0.1', 0), Handler) as server:
        server.interface = args.interface
        threading.Thread(target=server.serve_forever, daemon=True).start()
        env = os.environ.copy()
        proxy = f'http://127.0.0.1:{server.server_address[1]}'
        for key in ('HTTPS_PROXY', 'https_proxy', 'HTTP_PROXY', 'http_proxy', 'ALL_PROXY', 'all_proxy'):
            env[key] = proxy
        for key in ('NO_PROXY', 'no_proxy'):
            env[key] = 'localhost,127.0.0.1,::1'
        env['TERMINAL_DNS_TRANSPORT'] = 'local-connect'
        env['TERMINAL_DNS_INTERFACE'] = args.interface or ''
        base = Path(__file__).resolve().parent
        adapter = str(base / 'bin')
        # Resolve before adding our own PATH adapter, including nested runDNS.
        original_path = os.pathsep.join(p for p in env.get('PATH', '').split(os.pathsep)
                                        if p != adapter)
        binary = shutil.which('codex', path=original_path)
        if binary:
            env['TERMINAL_DNS_CODEX_BINARY'] = binary
        env['TERMINAL_DNS_BIN'] = adapter
        env['PATH'] = adapter + os.pathsep + original_path
        if Path(command[0]).name == 'bash' and command[1:] == ['-i']:
            command = [command[0], '--rcfile', str(base / 'bashrc'), '-i']
        # Explicit paths should use the same scoped behavior as PATH lookup.
        if binary and Path(command[0]).name == 'codex' and command[0] != 'codex':
            command = [str(base / 'bin' / 'codex')] + command[1:]
        child = subprocess.Popen(command, env=env)
        # Both processes share the terminal's foreground process group. The child
        # receives Ctrl+C directly; keep its proxy alive when the shell survives.
        previous = signal.signal(signal.SIGINT, lambda *_: None)
        try:
            returncode = child.wait()
            return returncode if returncode >= 0 else 128 - returncode
        finally:
            signal.signal(signal.SIGINT, previous)
            server.shutdown()


if __name__ == '__main__':
    raise SystemExit(main())
