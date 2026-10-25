"""Mutually pinned TLS 1.3 inference transport, independent of tool namespaces.

Only the root CPU coordinator owns client keys. The remote endpoint exposes one
bounded chat route to a loopback model server, never a shell or evaluation data.
No provider operations or model allocation are implemented in this module.
"""
import contextlib
from dataclasses import dataclass
import hashlib
import http.client
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import ipaddress
import json
import math
import os
from pathlib import Path
import select
import socket
import ssl
import stat
import subprocess
import threading
import time

BODY_LIMIT = 8 * 1024**2
RESPONSE_LIMIT = 16 * 1024**2
SERVER_NAME = 'backtrace-inference'


def private_file(path):
    path = Path(path)
    info = path.lstat()
    if not stat.S_ISREG(info.st_mode) or info.st_uid != os.geteuid() or info.st_mode & 0o077:
        raise ValueError('owner-only regular transport material required')
    return path


def fingerprint(path):
    return hashlib.sha256(ssl.PEM_cert_to_DER_cert(Path(path).read_text())).hexdigest()


def credentials(root):
    """Fresh, two-sided leaf pins; no CA/key from an account or agent input."""
    root = Path(root).absolute(); root.mkdir(mode=0o700)
    for name, purpose in (('server', 'serverAuth'), ('client', 'clientAuth')):
        subprocess.run(['openssl', 'req', '-x509', '-newkey', 'ed25519', '-nodes',
            '-keyout', str(root/(name+'.key')), '-out', str(root/(name+'.crt')),
            '-days', '2', '-subj', '/CN='+SERVER_NAME,
            '-addext', 'subjectAltName=DNS:'+SERVER_NAME,
            '-addext', 'extendedKeyUsage='+purpose],
            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
            check=True, timeout=10)
        for suffix in ('.crt', '.key'): (root/(name+suffix)).chmod(0o600)
    return {'server_sha256': fingerprint(root/'server.crt'),
            'client_sha256': fingerprint(root/'client.crt')}


class PinnedConnection(http.client.HTTPSConnection):
    def __init__(self, endpoint, timeout):
        self.endpoint = endpoint
        super().__init__(endpoint.host, endpoint.port, timeout=timeout, context=endpoint.context())

    def connect(self):
        deadline=time.monotonic()+self.timeout
        raw = socket.create_connection((self.host, self.port), self.timeout)
        try:
            left=deadline-time.monotonic()
            if left<=0: raise TimeoutError('inference TLS deadline')
            raw.settimeout(left)
            self.sock = self._context.wrap_socket(raw, server_hostname=SERVER_NAME)
            if hashlib.sha256(self.sock.getpeercert(binary_form=True)).hexdigest() != self.endpoint.server_sha256:
                raise ssl.SSLError('inference server identity mismatch')
        except BaseException:
            raw.close()
            if self.sock: self.sock.close()
            raise


@dataclass(frozen=True)
class Endpoint:
    host: str
    port: int
    material: Path
    server_sha256: str

    def __post_init__(self):
        # A resolved literal prevents DNS changes and environment proxy routing.
        ipaddress.ip_address(self.host)
        if type(self.port) is not int or not 1 <= self.port <= 65535:
            raise ValueError('explicit inference port required')
        if fingerprint(private_file(self.material/'server.crt')) != self.server_sha256:
            raise ValueError('server certificate pin mismatch')

    def context(self):
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        ctx.minimum_version = ctx.maximum_version = ssl.TLSVersion.TLSv1_3
        ctx.load_verify_locations(cafile=private_file(self.material/'server.crt'))
        ctx.load_cert_chain(private_file(self.material/'client.crt'), private_file(self.material/'client.key'))
        return ctx

    def connection(self, timeout):
        return PinnedConnection(self, timeout)

    def identity(self):
        return {'transport': 'TLS1.3_MUTUAL_LEAF_PINS', 'server_sha256': self.server_sha256,
                'client_sha256': fingerprint(self.material/'client.crt'),
                'route': '/v1/chat/completions'}


class TLSService(ThreadingHTTPServer):
    daemon_threads = False
    block_on_close = True

    def process_request_thread(self, request, client_address):
        # Headers/body have an absolute admission deadline as well as socket
        # timeouts. A slow trickle cannot extend shutdown or request admission.
        timer=threading.Timer(2,self.close_connection_socket,args=(request,))
        timer.daemon=True
        with self.active_lock:
            self.admission_timers[request]=timer;self.connections.add(request)
        timer.start()
        try: super().process_request_thread(request,client_address)
        finally:
            timer.cancel()
            with self.active_lock:
                self.admission_timers.pop(request,None);self.connections.discard(request)

    def get_request(self):
        raw, address = super().get_request()
        raw.settimeout(2)
        try:
            conn = self.context.wrap_socket(raw, server_side=True)
            if hashlib.sha256(conn.getpeercert(binary_form=True)).hexdigest() != self.client_sha256:
                conn.close(); raise ssl.SSLError('inference client identity mismatch')
            return conn, address
        except BaseException:
            raw.close(); raise


@contextlib.contextmanager
def inference_proxy(material, upstream_port, *, host='127.0.0.1', port=0, lifetime=10800):
    """Default-OCI compatible; the trusted upstream is never remotely bound.

    A finite process lifetime is additional containment, not provider deletion.
    Per-request cancellation closes both sockets, including a stalled upstream.
    """
    if type(upstream_port) is not int or not 1 <= upstream_port <= 65535:
        raise ValueError('loopback model port required')
    if not math.isfinite(lifetime) or not 0 < lifetime <= 10800:
        raise ValueError('bounded server lifetime required')
    material = Path(material)
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.minimum_version = context.maximum_version = ssl.TLSVersion.TLSv1_3
    context.load_cert_chain(private_file(material/'server.crt'), private_file(material/'server.key'))
    context.load_verify_locations(cafile=private_file(material/'client.crt'))
    context.verify_mode = ssl.CERT_REQUIRED
    client_pin = fingerprint(material/'client.crt')
    end = time.monotonic()+lifetime
    state = {'requests': 0, 'finished': 0, 'active': 0, 'cancelled': 0, 'errors': 0, 'attempts': []}
    lock = threading.Lock(); connections = set(); stopping = threading.Event()

    def close(sock):
        with contextlib.suppress(OSError): sock.shutdown(socket.SHUT_RDWR)

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args): pass

        def do_POST(self):
            upstream = None; upstream_socket = None; monitor = None
            done = threading.Event(); admitted = False; size = 0
            try:
                lengths = self.headers.get_all('Content-Length', [])
                limits = self.headers.get_all('X-Backtrace-Seconds', [])
                if (self.path != '/v1/chat/completions' or self.headers.get('Transfer-Encoding')
                        or len(lengths)!=1 or not lengths[0].isdigit()
                        or not 0 < int(lengths[0]) <= BODY_LIMIT or len(limits)!=1):
                    raise ValueError('bounded inference request required')
                seconds = float(limits[0])
                if not math.isfinite(seconds) or not 0 < seconds <= 300:
                    raise ValueError('bounded work time required')
                deadline = min(time.monotonic()+seconds, end)
                self.connection.settimeout(min(2, seconds))
                data = self.rfile.read(int(lengths[0]))
                if len(data)!=int(lengths[0]): raise ValueError('truncated request')
                with lock:
                    server.admission_timers[self.connection].cancel()
                    if stopping.is_set() or state['active'] >= 8 or state['requests']>=1500:
                        raise ValueError('inference unavailable')
                    state['requests'] += 1; state['active'] += 1; admitted = True
                    attempt={'sha256':hashlib.sha256(data).hexdigest(),'bytes':len(data),'http_status':None}
                    state['attempts'].append(attempt)
                    connections.add(self.connection)
                upstream = http.client.HTTPConnection('127.0.0.1', upstream_port,
                    timeout=max(.001, deadline-time.monotonic()))
                upstream.connect(); upstream_socket = upstream.sock
                with lock: connections.add(upstream_socket)

                def watch():
                    while not done.wait(.05):
                        expired = time.monotonic() >= deadline or stopping.is_set()
                        if not expired:
                            try:
                                readable, _, _ = select.select([self.connection], [], [], 0)
                                if readable:
                                    # No pipelining is permitted. EOF or extra input cancels.
                                    self.connection.recv(1); expired = True
                            except (OSError, ValueError): expired = True
                        if expired:
                            with lock: state['cancelled'] += 1
                            close(upstream_socket); close(self.connection); return
                monitor = threading.Thread(target=watch, daemon=True); monitor.start()
                upstream.request('POST', self.path, body=data, headers={
                    'Content-Type': 'application/json', 'Authorization': 'Bearer EMPTY',
                    'Accept-Encoding': 'identity', 'Connection': 'close'})
                response = upstream.getresponse()
                with lock:attempt['http_status']=response.status
                self.send_response(response.status)
                self.send_header('Content-Type', response.getheader('Content-Type', 'application/json'))
                self.send_header('Connection', 'close'); self.end_headers()
                while not response.isclosed():
                    left = deadline-time.monotonic()
                    if left <= 0: raise TimeoutError('inference deadline')
                    upstream_socket.settimeout(left)
                    chunk = response.read1(65536)
                    if not chunk: break
                    size += len(chunk)
                    if size > RESPONSE_LIMIT: raise ValueError('inference response bound')
                    self.connection.settimeout(min(2, max(.001, deadline-time.monotonic())))
                    self.wfile.write(chunk); self.wfile.flush()
            except Exception:
                with lock: state['errors'] += 1
                if not admitted:
                    with contextlib.suppress(OSError): self.send_error(400, 'Invalid inference envelope')
            finally:
                done.set()
                if monitor: monitor.join(timeout=3)
                if upstream: upstream.close()
                with lock:
                    connections.discard(upstream_socket); connections.discard(self.connection)
                    if admitted: state['active'] -= 1; state['finished'] += 1
                self.close_connection = True

    server = TLSService((host, port), Handler)
    server.context = context; server.client_sha256 = client_pin
    server.active_lock=lock;server.connections=connections
    server.admission_timers={};server.close_connection_socket=close
    thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()

    def stop():
        stopping.set()
        with lock:
            for connection in connections: close(connection)
        server.shutdown()

    timer = threading.Timer(lifetime, stop); timer.daemon = True; timer.start()
    try:
        yield server.server_port, state
    finally:
        timer.cancel(); stop(); server.server_close(); thread.join(timeout=3)
        if thread.is_alive() or state['active']:
            raise RuntimeError('inference proxy did not stop')
