"""FusionBridge: local HTTP bridge so an external tool (Claude Code) can drive Fusion 360.

Listens on 127.0.0.1 only. Every request must carry the token written to ~/.fusion_bridge/token
(header "X-Token"). Requests are handed to Fusion's main thread through a CustomEvent, because the
Fusion API may only be called from the main thread.

Endpoints (JSON in / JSON out):
  GET  /ping                      -> {"ok": true, "document": "...", "version": "..."}
  POST /exec   {"code": "..."}    -> runs Python on the main thread. Globals: adsk, app, ui, design, root,
                                     load_script(path). Assign to `result` to return a value. stdout is captured.
  POST /screenshot {"path": "/abs/file.png", "width": 1600, "height": 1000, "view": "iso|front|top|right|home|current",
                    "fit": true}     -> saves the active viewport as an image.

Stop the add-in in Shift+S > Add-Ins to close the port.
"""

import importlib.util
import io
import json
import os
import queue
import secrets
import sys
import threading
import traceback
import uuid
from contextlib import redirect_stdout
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import adsk.core
import adsk.fusion

HOST = '127.0.0.1'
PORT = int(os.environ.get('FUSION_BRIDGE_PORT', '7655'))
EVENT_ID = 'FusionBridgeExecEvent'
STATE_DIR = os.path.join(os.path.expanduser('~'), '.fusion_bridge')
TIMEOUT_S = 120

_app = None
_ui = None
_server = None
_server_thread = None
_custom_event = None
_handlers = []          # keep handler references alive
_jobs = {}              # job_id -> {"kind", "payload", "done": Event, "response"}
_jobs_lock = threading.Lock()
_token = None


# ---------------------------------------------------------------- main-thread work
def _active_design():
    return adsk.fusion.Design.cast(_app.activeProduct)


def _load_script(path):
    """Import a Fusion script file as a module (fresh each call) so its functions can be called."""
    name = 'bridge_' + os.path.splitext(os.path.basename(path))[0]
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def _do_exec(payload):
    code = payload.get('code', '')
    design = _active_design()
    env = {
        'adsk': adsk,
        'app': _app,
        'ui': _ui,
        'design': design,
        'root': design.rootComponent if design else None,
        'load_script': _load_script,
        'result': None,
    }
    buf = io.StringIO()
    try:
        with redirect_stdout(buf):
            exec(compile(code, '<bridge>', 'exec'), env)
        res = env.get('result')
        try:
            json.dumps(res)
        except TypeError:
            res = repr(res)
        return {'ok': True, 'stdout': buf.getvalue(), 'result': res}
    except Exception:
        return {'ok': False, 'stdout': buf.getvalue(), 'error': traceback.format_exc()}


_VIEWS = {
    'iso': 'IsoTopRightViewOrientation',
    'iso_left': 'IsoTopLeftViewOrientation',
    'front': 'FrontViewOrientation',
    'back': 'BackViewOrientation',
    'top': 'TopViewOrientation',
    'bottom': 'BottomViewOrientation',
    'right': 'RightViewOrientation',
    'left': 'LeftViewOrientation',
}


def _do_screenshot(payload):
    try:
        vp = _app.activeViewport
        view = payload.get('view', 'iso')
        if view == 'home':
            vp.goHome()
        elif view in _VIEWS:
            cam = vp.camera
            cam.viewOrientation = getattr(adsk.core.ViewOrientations, _VIEWS[view])
            cam.isFitView = True
            vp.camera = cam
        if payload.get('fit', True):
            vp.fit()
        path = payload.get('path') or os.path.join(STATE_DIR, 'shot.png')
        ok = vp.saveAsImageFile(path, int(payload.get('width', 1600)), int(payload.get('height', 1000)))
        return {'ok': bool(ok), 'path': path}
    except Exception:
        return {'ok': False, 'error': traceback.format_exc()}


class _ExecHandler(adsk.core.CustomEventHandler):
    def notify(self, args):
        job_id = args.additionalInfo
        with _jobs_lock:
            job = _jobs.get(job_id)
        if job is None:
            return
        try:
            if job['kind'] == 'exec':
                job['response'] = _do_exec(job['payload'])
            elif job['kind'] == 'screenshot':
                job['response'] = _do_screenshot(job['payload'])
            elif job['kind'] == 'ping':
                doc = _app.activeDocument
                job['response'] = {'ok': True, 'document': doc.name if doc else None, 'version': _app.version}
            else:
                job['response'] = {'ok': False, 'error': 'unknown kind'}
        except Exception:
            job['response'] = {'ok': False, 'error': traceback.format_exc()}
        finally:
            job['done'].set()


def _submit(kind, payload):
    job_id = uuid.uuid4().hex
    job = {'kind': kind, 'payload': payload, 'done': threading.Event(), 'response': None}
    with _jobs_lock:
        _jobs[job_id] = job
    try:
        _app.fireCustomEvent(EVENT_ID, job_id)
        if not job['done'].wait(payload.get('timeout', TIMEOUT_S) if isinstance(payload, dict) else TIMEOUT_S):
            return {'ok': False, 'error': 'timed out waiting for Fusion main thread (is a dialog open?)'}
        return job['response']
    finally:
        with _jobs_lock:
            _jobs.pop(job_id, None)


# ---------------------------------------------------------------- HTTP server (background thread)
class _Http(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def _send(self, code, obj):
        body = json.dumps(obj).encode('utf-8')
        self.send_response(code)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _authorized(self):
        if not secrets.compare_digest(self.headers.get('X-Token', ''), _token):
            self._send(403, {'ok': False, 'error': 'bad token'})
            return False
        return True

    def do_GET(self):
        if not self._authorized():
            return
        if self.path == '/ping':
            self._send(200, _submit('ping', {}))
        else:
            self._send(404, {'ok': False, 'error': 'not found'})

    def do_POST(self):
        if not self._authorized():
            return
        length = int(self.headers.get('Content-Length', '0'))
        try:
            payload = json.loads(self.rfile.read(length) or b'{}')
        except ValueError:
            self._send(400, {'ok': False, 'error': 'bad json'})
            return
        if self.path == '/exec':
            self._send(200, _submit('exec', payload))
        elif self.path == '/screenshot':
            self._send(200, _submit('screenshot', payload))
        else:
            self._send(404, {'ok': False, 'error': 'not found'})


# ---------------------------------------------------------------- add-in lifecycle
def run(context):
    global _app, _ui, _server, _server_thread, _custom_event, _token
    try:
        _app = adsk.core.Application.get()
        _ui = _app.userInterface

        os.makedirs(STATE_DIR, mode=0o700, exist_ok=True)
        _token = secrets.token_hex(24)
        token_path = os.path.join(STATE_DIR, 'token')
        with open(token_path, 'w') as f:
            f.write(_token)
        os.chmod(token_path, 0o600)
        with open(os.path.join(STATE_DIR, 'port'), 'w') as f:
            f.write(str(PORT))

        _custom_event = _app.registerCustomEvent(EVENT_ID)
        handler = _ExecHandler()
        _custom_event.add(handler)
        _handlers.append(handler)

        _server = ThreadingHTTPServer((HOST, PORT), _Http)
        _server.daemon_threads = True
        _server_thread = threading.Thread(target=_server.serve_forever, daemon=True)
        _server_thread.start()
    except Exception:
        if _ui:
            _ui.messageBox('FusionBridge failed to start:\n{}'.format(traceback.format_exc()))


def stop(context):
    global _server, _custom_event
    try:
        if _server:
            _server.shutdown()
            _server.server_close()
            _server = None
        if _custom_event:
            for h in _handlers:
                _custom_event.remove(h)
            _handlers.clear()
            _app.unregisterCustomEvent(EVENT_ID)
            _custom_event = None
        token_path = os.path.join(STATE_DIR, 'token')
        if os.path.exists(token_path):
            os.remove(token_path)
    except Exception:
        if _ui:
            _ui.messageBox('FusionBridge stop error:\n{}'.format(traceback.format_exc()))
