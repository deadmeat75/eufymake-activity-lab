"""Bounded, persistent and credential-free activity observations."""
from collections import Counter, OrderedDict
from copy import deepcopy
from datetime import datetime, timezone
from uuid import uuid4
import math
import hashlib
import json
import re
import time
from .telemetry import utc
from .interpretation import Interpretation


SENSITIVE = re.compile(r"secret|token|password|credential|cert|email|username|user_id|station_sn|serial|private|url|uri|path|filename|account|device_id|(^|_)id($|_)|guid|uuid|address|host|ip_address|api_key|auth|login|session|(^|_)uid($|_)|mac_address|ssid|(^|_)sn($|_)", re.I)


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
        self.events = list(saved.get('events', []))[-self.limit:]
        self.recordings = list(saved.get('recordings', []))[-100:]
        self.active_recording = saved.get('active_recording')
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
        self.seen_reports = OrderedDict()
        self.last_capture = {}
        self.interpretation = Interpretation(saved.get('interpretation'))
        if 'interpretation' not in saved:
            for event in sorted(self.events, key=lambda e: e.get('time', '')):
                if isinstance(event.get('fields'), dict):
                    self.interpretation.observe(event['fields'], event.get('time'))
        if 'insights' not in (saved.get('interpretation') or {}):
            from .insights import Insights
            self.interpretation.insights = Insights()
            # Backfill bounded summaries from retained redacted observations on upgrade.
            # Do not rewrite original IDs, notes, fields or event timestamps.
            for event in sorted(self.events, key=lambda e: e.get('time', '')):
                if event.get('kind') in ('connection','session'):
                    self.interpretation.insights.connection_event(event.get('detail') == 'connected', event.get('time'))
                elif isinstance(event.get('fields'), dict):
                    self.interpretation.insights.observe(event['fields'], event.get('time'))
        history = self.interpretation.insights
        history.pair = history.job = history.operation = history.ink = None
        history.connection = history.connection_time = None
        self._add('session', detail='Home Assistant monitor started')

    def _add(self, kind, **fields):
        timestamp = fields.pop('_time', None) or utc_now()
        if kind in ('status', 'connection', 'recording') and not fields.get('historical') and self.active_status:
            previous = next((e for e in reversed(self.events) if e['id'] == self.active_status), None)
            if previous:
                previous['revision'] = previous.get('revision', 1) + 1
                previous['duration_seconds'] = max(0, round((datetime.fromisoformat(timestamp) - datetime.fromisoformat(previous['time'])).total_seconds(), 1))
            self.active_status = None
        event = {'id': uuid4().hex, 'time': timestamp, 'session': self.session, 'revision': 1, 'kind': kind, **fields}
        if self.active_recording:
            event['recording_session'] = self.active_recording
        self.events.append(event)
        if len(self.events) > 1 and timestamp < self.events[-2]['time']:
            self.events.sort(key=lambda e: e['time'])
        while len(self.events) > self.limit:
            self.events.pop(0)
            self.dropped += 1
        if kind == 'status' and not fields.get('historical'):
            self.active_status = event['id']
        return event

    def receive(self, kind, payload=None, observed_at=None):
        timestamp = utc(observed_at) if observed_at is not None else utc(utc_now())
        if timestamp is None:
            return False
        if kind == 'diagnostic':
            if not isinstance(payload, dict) or not isinstance(payload.get('reason'), str):
                return False
            self.diagnostics[payload['reason'][:64]] += 1
            return False
        if kind != 'message':
            connected = kind == 'connected'
            if connected != self.connected or kind == 'auth_failed':
                self._add('connection', _time=timestamp, detail=kind)
            self.interpretation.insights.connection_event(connected, timestamp)
            self.connected = connected
            self.current = None
            self.interpretation.readings.clear()
            self.interpretation.progress = None
            self.last_status = None
            return True
        timestamp = utc(observed_at) if observed_at is not None else utc(utc_now())
        if not isinstance(payload, dict) or timestamp is None:
            return False
        self.messages += 1
        self.last_received = max(self.last_received or timestamp, timestamp)
        command = payload.get('commandType')
        command_key = str(command) if type(command) is int and 0 <= command <= 65535 else 'unspecified'
        if command_key not in self.total_commands and len(self.total_commands) >= 256:
            command_key = 'other'
        self.commands[command_key] += 1
        self.total_commands[command_key] += 1
        fields = safe_fields(payload)
        if observed_at is not None:
            fingerprint = hashlib.sha256((timestamp + json.dumps(fields,sort_keys=True)).encode()).hexdigest()
            if fingerprint in self.seen_reports:
                return False
            self.seen_reports[fingerprint] = True
            if len(self.seen_reports) > 4096:
                self.seen_reports.popitem(last=False)
        detail, historical = self.interpretation.observe(payload, timestamp)
        known = command in (1000, 1001, 1068, 1100)
        if known and not historical:
            self.live[command_key] = {'time': timestamp, 'fields': fields}
        if command == 1000 and isinstance(payload.get('status'), dict):
            status = payload['status']
            state, step = status.get('state'), status.get('step')
            if type(state) is int and type(step) is int:
                pair = (state, step)
                if not historical:
                    self.current = {'state': state, 'step': step}
                if pair != self.last_status or historical:
                    if not historical:
                        self.last_status = pair
                    if self.recording:
                        if not historical:
                            self.last_data[command_key] = fields
                        self._add('status', _time=timestamp, historical=historical, state=state, step=step, command=command, fields=fields, detail=detail, note='')
                        return True
        enabled = self.capture_telemetry if known else self.capture_unknown
        changed = self.last_data.get(command_key) != fields
        now = time.monotonic()
        if self.recording and enabled and changed and (command in (1118,1153) or historical or now - self.last_capture.get(command_key, -10) >= 5):
            if not historical:
                self.last_data[command_key] = fields
            self.last_capture[command_key] = now
            if command != 1000 or changed:
                self._add('telemetry' if known else 'unknown', _time=timestamp, historical=historical, detail=detail, command=command if type(command) is int else None, fields=fields, note='')
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

    def bookmark(self, event_id, enabled):
        if type(enabled) is not bool:
            raise ValueError('Bookmark must be true or false')
        for event in self.events:
            if event['id'] == event_id:
                event['bookmark'] = enabled
                event['revision'] = event.get('revision', 1) + 1
                return
        raise ValueError('Record no longer exists')

    def recording_session(self, name=None, note='', end=False):
        timestamp = utc(utc_now())
        if not isinstance(note, str) or len(note) > 1000:
            raise ValueError('Session notes must contain at most 1000 characters')
        if type(end) is not bool:
            raise ValueError('Session end must be true or false')
        if end:
            record = next((r for r in self.recordings if r['id'] == self.active_recording), None)
            if record:
                record['end'] = timestamp
                if note.strip():
                    record['end_note'] = note.strip()
                self._add('marker', note='Recording session ended: ' + record['name'])
            self.active_recording = None
            return
        if self.active_recording:
            raise ValueError('End the current named session first')
        if not isinstance(name, str) or not 1 <= len(name.strip()) <= 120:
            raise ValueError('Enter a session name of at most 120 characters')
        record = {'id': uuid4().hex, 'name': name.strip(), 'note': note.strip(), 'start': timestamp}
        self.recordings.append(record)
        self.recordings = self.recordings[-100:]
        self.active_recording = record['id']
        self._add('marker', note='Recording session started: ' + record['name'])

    def compare(self, first, second):
        events = {e['id']:e for e in self.events if e['id'] in (first, second)}
        if len(events) != 2:
            raise ValueError('Select two different retained records')
        def flatten(value, path='$'):
            if isinstance(value, dict) and value:
                return {k:v for key,item in value.items() for k,v in flatten(item, path + '.' + key).items()}
            if isinstance(value, list) and value:
                return {k:v for index,item in enumerate(value) for k,v in flatten(item, path + '[' + str(index) + ']').items()}
            return {path:value}
        a, b = flatten(events[first].get('fields', {})), flatten(events[second].get('fields', {}))
        changes = [{'field':k,'before':a.get(k),'after':b.get(k),'before_present':k in a,'after_present':k in b} for k in sorted(a.keys() | b.keys()) if k not in a or k not in b or a[k] != b[k]]
        return {'first':first,'second':second,'first_time':events[first]['time'],'second_time':events[second]['time'],'changes':changes}

    def saved(self):
        return deepcopy({'recordings': self.recordings, 'active_recording': self.active_recording, 'events': self.events, 'interpretation': self.interpretation.saved(), 'labels': self.labels,
                         'recording': self.recording, 'dropped': self.dropped, 'limit': self.limit,
                         'total_commands': dict(self.total_commands), 'capture_telemetry': self.capture_telemetry, 'capture_unknown': self.capture_unknown})

    def snapshot(self, export=False, recording_session=None):
        events = self.events
        if recording_session:
            if not any(r['id'] == recording_session for r in self.recordings):
                raise ValueError('Recording session no longer exists')
            events = [e for e in events if e.get('recording_session') == recording_session]
        counts = Counter(f"{e['state']}/{e['step']}" for e in events if e['kind'] == 'status')
        if recording_session:
            return {'version':1, 'export_recording_session':recording_session, 'exported_records':len(events),
                    'retention_dropped_total':self.dropped, 'events':deepcopy(events), 'pairs':dict(counts),
                    'labels':deepcopy({k:v for k,v in self.labels.items() if k in counts}),
                    'recordings':deepcopy([r for r in self.recordings if r['id']==recording_session])}
        return {'recordings': deepcopy(self.recordings), 'active_recording': self.active_recording,
                'export_recording_session': recording_session, 'exported_records': len(events) if export else None,
                'bookmarks': sum(bool(e.get('bookmark')) for e in self.events), 'version': 1, 'connected': self.connected, 'recording': self.recording,
                'current': self.current, 'last_received': self.last_received,
                'decoded': deepcopy(self.interpretation.snapshot()),
                'live': deepcopy(self.live), 'diagnostics': dict(self.diagnostics),
                'total_commands': dict(self.total_commands), 'capture_telemetry': self.capture_telemetry, 'capture_unknown': self.capture_unknown,
                'messages_this_session': self.messages, 'commands_this_session': dict(self.commands),
                'retained': len(self.events), 'limit': self.limit, 'dropped': self.dropped,
                'labels': deepcopy(self.labels), 'pairs': dict(counts),
                'events': deepcopy(events if export else events[-300:])}
