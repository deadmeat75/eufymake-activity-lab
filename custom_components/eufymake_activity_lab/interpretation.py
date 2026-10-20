"""Human-readable interpretation alongside (never instead of) redacted raw records."""
from .telemetry import Hardware, OPERATIONS, STATUS, number, utc, transition


class Interpretation:
    def __init__(self, saved=None):
        saved = saved or {}
        self.hardware = Hardware(saved.get('hardware'))
        self.pair = tuple(saved['pair']) if saved.get('pair') else None
        self.clocks = dict(saved.get('clocks', {}))
        self.progress = None  # Never infer completion from a prior connection/session.
        self.readings = {}  # Session freshness is not restored across restarts.

    def saved(self):
        return {'hardware': self.hardware.reports, 'pair': self.pair,
                'clocks': self.clocks, 'progress': self.progress}

    def observe(self, payload, timestamp):
        if not isinstance(payload, dict):
            return '', False
        command = payload.get('commandType')
        if type(command) is not int or command not in (1000,1001,1068,1100,1105,1118,1133,1136,1148,1153,1155):
            return '', False
        timestamp = utc(timestamp)
        if timestamp is None:
            return '', True
        if timestamp < self.clocks.get(str(command), timestamp):
            return 'Historical report (out of order; current state unchanged)', True
        self.clocks[str(command)] = timestamp
        if command == 1000:
            status = payload.get('status')
            if not isinstance(status, dict) or type(status.get('state')) is not int or type(status.get('step')) is not int:
                return '', False
            pair = (status['state'], status['step'])
            detail = transition(self.pair, pair, self.progress) if self.pair != pair else ''
            if pair != self.pair and pair not in ((2,3),(2,4)):
                self.progress = None
                self.readings.pop('1001', None)
            if pair == (2,4) and self.pair not in ((2,3),(2,4)):
                self.progress = None
                self.readings.pop('1001', None)
            if pair != self.pair:
                self.readings.pop('activity', None)
            self.pair = pair
            self.readings['status'] = {'time': timestamp, 'label': STATUS.get(pair, 'Unknown (%s/%s)' % pair)}
            return detail, False
        if command in (1118,1153):
            before = self.hardware.identity()
            self.hardware.observe(payload, timestamp)
            after = self.hardware.identity()
            if before == after or after is None:
                return '', False
            config = self.hardware.configuration()
            if after == 'none':
                name = {'mini':'Mini Flatbed','standard':'Standard Flatbed','rotary':'Rotary'}.get(before, 'Accessory')
                return ('No bed detected' if before is None else name + ' no longer detected; check installation and locking latch'), False
            return config['effective'] + (' reported' if before is None else ' detected'), False
        if command == 1001 and self.pair in ((2,3),(2,4)):
            self.progress = payload.get('progress') if number(payload.get('progress')) is not None else None
            self.readings['1001'] = {'time': timestamp, 'fields': {k: (number(payload.get(k)) if number(payload.get(k)) is not None and number(payload.get(k)) >= 0 and (k != 'progress' or number(payload.get(k)) <= 10000) else None) for k in ('progress','time','totalTime')}}
        expected = 1105 if self.pair == (8,0) else OPERATIONS.get(self.pair,(None,None))[1]
        if command == expected and timestamp >= self.clocks.get('1000',timestamp):
            progress = number(payload.get('progress'))
            self.readings['activity'] = {'time': timestamp, 'progress': progress if progress is not None and 0 <= progress <= 100 else None,
                                         'operation': STATUS.get(self.pair), 'source_command': command}
        return '', False

    def snapshot(self):
        return {'hardware': self.hardware.configuration(), 'readings': self.readings,
                'status': STATUS.get(self.pair, 'Unknown (%s/%s)' % self.pair) if self.pair else None}
