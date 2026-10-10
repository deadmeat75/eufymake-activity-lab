"""Bounded, persistent and credential-free activity observations."""
from collections import Counter
from copy import deepcopy
from datetime import datetime, timezone
from uuid import uuid4
import math
import re
import time


SENSITIVE = re.compile(r"secret|token|password|credential|cert|email|username|user_id|station_sn|serial|private|url|uri|path|filename|account|device_id|(^|_)id($|_)|guid|uuid|address|host|ip_address|api_key|auth|login|session|(^|_)uid($|_)|mac_address|ssid", re.I)


def safe_fields(value, depth=0):
    """Keep numeric observations and shape; omit strings and identifiable fields."""
    if depth > 5:
        return '<depth limit>'
    if isinstance(value, dict):
        result = {}
        for key, item in list(value.items())[:64]:
            if not isinstance(key, str) or not re.fullmatch(r'[A-Za-z][A-Za-z0-9_]{0,63}', key) or SENSITIVE.search(key):
                continue
            result[key] = safe_fields(item, depth + 1)
        return result
    if isinstance(value, list):
        result = [safe_fields(item, depth + 1) for item in value[:24]]
        if len(value) > 24:
            result.append('<list truncated>')
        return result
    if value is None or type(value) is bool:
        return value
    if type(value) in (int, float):
        if type(value) is int and abs(value) > 10**12:
            return '<large integer>'
        return value if math.isfinite(value) else None
    if isinstance(value, str):
        return '<text omitted>'
    return '<unsupported>'


def utc_now():
    return datetime.now(timezone.utc).isoformat()


class Recorder:
    def __init__(self, saved=None, limit=10000):
        saved = saved or {}
        self.limit = saved.get('limit', limit)
        self.events = list(saved.get('events', []))[-limit:]
        self.labels = dict(saved.get('labels', {}))
        self.recording = bool(saved.get('recording', True))
        self.dropped = int(saved.get('dropped', 0))
        self.connected = False
        self.current = None
        self.last_received = None
        self.messages = 0
        self.commands = Counter()
        self.session = uuid4().hex
        self.last_status = None
        self.active_status = None
        self.live = {}
        self.diagnostics = Counter()
        self.total_commands = Counter(saved.get('total_commands', {}))
        self.capture_telemetry = bool(saved.get('capture_telemetry', True))
        self.capture_unknown = bool(saved.get('capture_unknown', True))
        self.last_data = {}
        self.last_capture = {}
        self._add('session', detail='Home Assistant monitor started')

    def _add(self, kind, **fields):
        if len(self.events) >= self.limit:
            self.events.pop(0)
            self.dropped += 1
        timestamp = utc_now()
        if kind in ('status', 'connection', 'recording') and self.active_status:
            previous = next((e for e in reversed(self.events) if e['id'] == self.active_status), None)
            if previous:
                previous['revision'] = previous.get('revision', 1) + 1
                previous['duration_seconds'] = max(0, round((datetime.fromisoformat(timestamp) - datetime.fromisoformat(previous['time'])).total_seconds(), 1))
            self.active_status = None
        event = {'id': uuid4().hex, 'time': timestamp, 'session': self.session, 'revision': 1, 'kind': kind, **fields}
        self.events.append(event)
        if kind == 'status':
            self.active_status = event['id']
        return event

    def receive(self, kind, payload=None):
        if kind == 'diagnostic':
            self.diagnostics[payload['reason']] += 1
            return False
        if kind != 'message':
            connected = kind == 'connected'
            if connected != self.connected or kind == 'auth_failed':
                self._add('connection', detail=kind)
            self.connected = connected
            self.last_status = None
            return True
        self.messages += 1
        self.last_received = utc_now()
        command = payload.get('commandType')
        command_key = str(command) if type(command) is int and 0 <= command <= 65535 else 'unspecified'
        if command_key not in self.total_commands and len(self.total_commands) >= 256:
            command_key = 'other'
        self.commands[command_key] += 1
        self.total_commands[command_key] += 1
        fields = safe_fields(payload)
        known = command in (1000, 1001, 1068, 1100)
        if known:
            self.live[command_key] = {'time': self.last_received, 'fields': fields}
        if command == 1000 and isinstance(payload.get('status'), dict):
            status = payload['status']
            state, step = status.get('state'), status.get('step')
            if type(state) is int and type(step) is int:
                pair = (state, step)
                self.current = {'state': state, 'step': step}
                if pair != self.last_status:
                    self.last_status = pair
                    if self.recording:
                        self._add('status', state=state, step=step, command=command, fields=fields, note='')
                        return True
        enabled = self.capture_telemetry if known else self.capture_unknown
        changed = self.last_data.get(command_key) != fields
        now = time.monotonic()
        if self.recording and enabled and changed and now - self.last_capture.get(command_key, -10) >= 5:
            self.last_data[command_key] = fields
            self.last_capture[command_key] = now
            if command != 1000:
                self._add('telemetry' if known else 'unknown', command=command if type(command) is int else None, fields=fields, note='')
                return True
        return False

    def settings(self, telemetry, unknown, retention=None):
        if type(telemetry) is not bool or type(unknown) is not bool:
            raise ValueError('Capture options must be true or false')
        if retention is not None:
            if type(retention) is not int or not 1000 <= retention <= 50000:
                raise ValueError('Retention must be between 1000 and 50000 records')
            self.limit = retention
            if len(self.events) > self.limit:
                self.dropped += len(self.events) - self.limit
                self.events = self.events[-self.limit:]
        self.capture_telemetry, self.capture_unknown = telemetry, unknown
        self.last_data.clear()
        self.last_capture.clear()

    def marker(self, note):
        if not isinstance(note, str) or not 1 <= len(note.strip()) <= 1000:
            raise ValueError('Enter an observation of at most 1000 characters')
        self._add('marker', note=note.strip())

    def annotate(self, event_id, note):
        if not isinstance(note, str) or len(note) > 1000:
            raise ValueError('Notes must contain at most 1000 characters')
        for event in self.events:
            if event['id'] == event_id:
                event['note'] = note.strip()
                event['revision'] = event.get('revision', 1) + 1
                return
        raise ValueError('Record no longer exists')

    def label(self, state, step, label, confidence):
        if type(state) is not int or type(step) is not int:
            raise ValueError('State and step must be integers')
        if not isinstance(label, str) or len(label) > 120 or confidence not in ('suspected', 'confirmed'):
            raise ValueError('Invalid label or confidence')
        key = f'{state}/{step}'
        if label.strip():
            if key not in self.labels and len(self.labels) >= 500:
                raise ValueError('Label limit reached')
            self.labels[key] = {'label': label.strip(), 'confidence': confidence}
        else:
            self.labels.pop(key, None)

    def set_recording(self, enabled):
        if type(enabled) is not bool:
            raise ValueError('Recording must be true or false')
        if self.recording != enabled:
            self.recording = enabled
            self.last_status = None
            self._add('recording', detail='resumed' if enabled else 'paused')

    def saved(self):
        return deepcopy({'events': self.events, 'labels': self.labels,
                         'recording': self.recording, 'dropped': self.dropped, 'limit': self.limit,
                         'total_commands': dict(self.total_commands), 'capture_telemetry': self.capture_telemetry, 'capture_unknown': self.capture_unknown})

    def snapshot(self, export=False):
        counts = Counter(f"{e['state']}/{e['step']}" for e in self.events if e['kind'] == 'status')
        return {'version': 1, 'connected': self.connected, 'recording': self.recording,
                'current': self.current, 'last_received': self.last_received,
                'live': deepcopy(self.live), 'diagnostics': dict(self.diagnostics),
                'total_commands': dict(self.total_commands), 'capture_telemetry': self.capture_telemetry, 'capture_unknown': self.capture_unknown,
                'messages_this_session': self.messages, 'commands_this_session': dict(self.commands),
                'retained': len(self.events), 'limit': self.limit, 'dropped': self.dropped,
                'labels': deepcopy(self.labels), 'pairs': dict(counts),
                'events': deepcopy(self.events if export else self.events[-300:])}
