"""Bounded observational history. No transport, machine actions or public identifiers."""
from copy import deepcopy
from datetime import datetime
import hashlib
import hmac
import secrets
from .telemetry import OPERATIONS, number, utc

COLORS = ('cyan', 'magenta', 'yellow', 'black', 'white', 'gloss')
PRINT = ((2, 3), (2, 4))


def seconds(start, end):
    return max(0, (datetime.fromisoformat(end) - datetime.fromisoformat(start)).total_seconds())


def values(value, maximum=None):
    if not isinstance(value, list) or len(value) < 6:
        return None
    result = value[:6]
    return result if all(number(v) is not None and v >= 0 and (maximum is None or v <= maximum) for v in result) else None


class Insights:
    """Persist summaries, never restore an active print/clean across a connection gap."""
    def __init__(self, saved=None):
        saved = saved if isinstance(saved, dict) else {}
        self.salt = saved.get('salt') or secrets.token_hex(32)
        self.identities = dict(saved.get('identities', {}))
        self.data = {key: deepcopy(saved.get(key, []))[-limit:] for key, limit in (
            ('prints', 20), ('maintenance', 30), ('connections', 50),
            ('ink_history', 720), ('cartridge_changes', 30))}
        self.pair = None
        self.job = None
        self.operation = None
        self.ink = None
        self.clocks = {}
        self.connection = None
        self.connection_time = None
        self.revision = 0
        self.last_signal = None

    def saved(self):
        return {**deepcopy(self.data), 'salt': self.salt, 'identities': dict(self.identities)}

    def public(self):
        # Neither stable identity hashes nor their salt leave the local history store.
        return deepcopy(self.data)

    def _append(self, key, value, limit):
        self.data[key].append(value)
        self.data[key] = self.data[key][-limit:]
        self.revision += 1

    def connection_event(self, connected, timestamp):
        timestamp = utc(timestamp)
        if timestamp is None or (self.connection_time and timestamp < self.connection_time):
            return
        if connected == self.connection:
            return
        record = {'time': timestamp, 'connected': connected}
        if self.connection_time:
            record['previous_duration_seconds'] = seconds(self.connection_time, timestamp)
            record['previous_connected'] = self.connection
        self._append('connections', record, 50)
        self.connection, self.connection_time = connected, timestamp
        if not connected:
            self.pair = None
            self.job = self.operation = self.ink = None
            self.last_signal = None

    def _baseline(self, timestamp):
        return deepcopy(self.ink) if self.ink and 0 <= seconds(self.ink['time'], timestamp) <= 120 and self.ink['time'] <= timestamp else None

    def _usage(self, context, timestamp):
        start, end = context.get('ink_start'), self._baseline(timestamp)
        if not start or not end or end['time'] < context['start'] or context.get('inventory_uncertain'):
            return {'status': 'Unavailable: incomplete readings, inventory increase or cartridge change'}
        delta = [round((a-b)/100, 4) for a,b in zip(start['levels'], end['levels'])]
        if any(v < 0 for v in delta):
            return {'status': 'Unavailable: inventory increased'}
        return {'status': 'Estimated inventory decrease; attribution may overlap adjacent activity',
                'estimated_ml': dict(zip(COLORS, delta)), 'total_estimated_ml': round(sum(delta), 4),
                'baseline_time': start['time'], 'end_reading_time': end['time']}

    def observe(self, item, timestamp):
        if not isinstance(item, dict) or type(item.get('commandType')) is not int:
            return
        timestamp = utc(timestamp)
        command = item['commandType']
        if timestamp is None or timestamp < self.clocks.get(command, timestamp):
            return
        # Messages predating the latest operating-state transition cannot alter its job.
        if command in (1001,1068,1140) and timestamp < self.clocks.get(1000, timestamp):
            return
        self.clocks[command] = timestamp
        if command == 1000:
            status = item.get('status')
            if not isinstance(status, dict) or any(type(status.get(k)) is not int for k in ('state','step')):
                return
            pair = status['state'], status['step']
            if pair == self.pair:
                return
            if self.operation:
                record = {**self.operation, 'end': timestamp, 'duration_seconds': round(seconds(self.operation['start'], timestamp), 1)}
                record['usage'] = self._usage(self.operation, timestamp)
                record.pop('ink_start', None)
                self._append('maintenance', record, 30)
                self.operation = None
            if self.job and pair not in PRINT:
                if pair == (0,0) and self.job.get('last_progress_time', timestamp) <= timestamp:
                    result = {**self.job, 'end': timestamp, 'completion_confirmed': self.job.get('progress') == 10000 and self.job.get('last_progress_time') is not None and self.job['last_progress_time'] <= timestamp and seconds(self.job['last_progress_time'],timestamp)<=120}
                    result['usage'] = self._usage(self.job, timestamp)
                    result.pop('ink_start', None)
                    self._append('prints', result, 20)
                self.job = None
            if pair == (2,4) and self.pair not in PRINT:
                self.job = {'start': timestamp, 'start_method': 'Unknown',
                            'ink_start': self._baseline(timestamp), 'progress': None,
                            'elapsed_seconds': None, 'remaining_seconds': None,
                            'inventory_uncertain': self.pair not in ((2,1),(2,2),(2,6))}
                if self.last_signal and self.last_signal <= timestamp and seconds(self.last_signal, timestamp) <= 120:
                    self.job['experimental_start_signal'] = {'command':1140,'time':self.last_signal,'meaning':'Unverified; does not identify the start method'}
            if pair in OPERATIONS:
                self.operation = {'start': timestamp, 'operation': OPERATIONS[pair][0],
                                  'source_command': OPERATIONS[pair][1], 'ink_start': self._baseline(timestamp),
                                  'inventory_uncertain': False}
            self.pair = pair
        elif command == 1001 and self.job and self.pair in PRINT:
            for source, target in (('progress','progress'),('time','remaining_seconds'),('totalTime','elapsed_seconds')):
                value = number(item.get(source))
                if value is not None and value >= 0 and (source != 'progress' or value <= 10000):
                    self.job[target] = value
            progress = number(item.get('progress'))
            if progress is not None and 0 <= progress <= 10000:
                self.job['last_progress_time'] = timestamp
        elif command == 1068 and self.job:
            quantities = {key: number(item.get(key)) for key in ('print_quantity','pump_quantity','pump_time','pump_number')}
            quantities = {key:value for key,value in quantities.items() if value is not None and value >= 0}
            channels = values(item.get('ink_quantity'))
            if channels:
                quantities['ink_quantity'] = channels
                quantities['six_channel_total'] = number(sum(channels))
            if quantities:
                self.job['reported_quantities'] = {'time':timestamp,'units':'Unverified', **quantities}
            elapsed = number(item.get('totalTime'))
            if self.job.get('elapsed_seconds') is None and elapsed is not None and elapsed >= 0:
                self.job['elapsed_seconds'] = elapsed
        elif command == 1140:
            self.last_signal = timestamp
        elif command == 1100:
            ink = item.get('ink')
            if not isinstance(ink, dict):
                return
            levels = values(ink.get('leftInk'), 10000)
            changed = False
            # Only explicitly named identity fields support a replacement claim.
            for identity_key in ('sn','serialNumber','cartridgeId'):
                identities = ink.get(identity_key)
                if not isinstance(identities, list):
                    continue
                for index, identity in enumerate(identities[:6]):
                    if type(identity) not in (str,int) or not str(identity).strip() or str(identity).startswith('<'):
                        continue
                    key = COLORS[index] + ':' + identity_key
                    digest = hmac.new(self.salt.encode(), str(identity).encode(), hashlib.sha256).hexdigest()
                    previous = self.identities.get(key)
                    if previous and previous != digest:
                        changed = True
                        expiry = ink.get('expirationTimestamp')
                        expiration = expiry[index] if isinstance(expiry,list) and len(expiry)>index and number(expiry[index]) is not None and 946684800 <= expiry[index] < 4102444800 else None
                        self._append('cartridge_changes', {'time':timestamp,'color':COLORS[index],
                            'level_percent':levels[index]/100 if levels else None,'expiration_timestamp':expiration},30)
                    if previous != digest:
                        self.identities[key] = digest
                        self.revision += 1
                break
            for context in (self.job,self.operation):
                if context and (changed or levels is None or (self.ink and (seconds(self.ink['time'],timestamp)>120 or any(b>a for a,b in zip(self.ink['levels'], levels or self.ink['levels']))))):
                    context['inventory_uncertain'] = True
            if levels:
                self.ink = {'time': timestamp, 'levels': levels}
                last = self.data['ink_history'][-1] if self.data['ink_history'] else None
                if changed or last is None or seconds(last['time'],timestamp)>=300:
                    self._append('ink_history', {'time':timestamp,'levels_percent':[v/100 for v in levels], 'cartridge_change':changed},720)
