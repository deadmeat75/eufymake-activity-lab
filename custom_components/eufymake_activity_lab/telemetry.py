"""Observed E1 telemetry meanings; pure Python, no transport or control actions."""
from datetime import datetime, timezone
import math

BEDS = {0: 'No bed detected', 1: 'Standard Flatbed', 2: 'Mini Flatbed', 3: 'Rotary'}
ACCESSORIES = {0: 'No accessory detected', 1: 'Mini Flatbed', 2: 'Standard Flatbed', 4: 'Rotary'}
IDENTITIES = {1118: {0: 'none', 1: 'standard', 2: 'mini', 3: 'rotary'},
              1153: {0: 'none', 1: 'mini', 2: 'standard', 4: 'rotary'}}
OPERATIONS = {(5, 7): ('Automatic flash clean', 1148),
              (5, 10): ('Automatic deep cleaning', 1155),
              (5, 9): ('Automatic moisturizing', 1155),
              (5, 3): ('Injecting ink', 1136)}
STATUS = {(0, 0): 'Idle', (2, 1): 'Transferring print file', (2, 2): 'Waiting for Start',
          (2, 3): 'Paused', (2, 4): 'Printing', (2, 6): 'Priming print head',
          (8, 0): 'Taking snapshot', (6, 1): 'Updating firmware', (9, 0): 'Calibration / self-check',
          (13, 0): 'Maintenance — ink injection required after moisturizing',
          (13, 1): 'Maintenance — inject ink before printing',
          **{pair: item[0] for pair, item in OPERATIONS.items()}}


def number(value):
    if type(value) not in (int, float):
        return None
    try:
        return value if math.isfinite(value) else None
    except OverflowError:
        return None


def code(value):
    return type(value) is int and 0 <= value <= 65535


def utc(value):
    """Only explicit aware observation timestamps, never job payload timestamps."""
    try:
        parsed = datetime.fromisoformat(value.replace('Z', '+00:00')) if isinstance(value, str) else value
        if not isinstance(parsed, datetime) or parsed.tzinfo is None:
            return None
        return parsed.astimezone(timezone.utc).isoformat(timespec='microseconds')
    except (ValueError, TypeError, OverflowError):
        return None


def label(table, value):
    return table.get(value, 'Unknown (%s)' % value) if code(value) else None


class Hardware:
    """Independent reports with no invented translation of reply across commands."""
    def __init__(self, saved=None):
        self.reports = dict(saved or {})
        self.private_metadata = {}  # Never serialized, logged or added to HA attributes.

    def observe(self, payload, timestamp):
        command = payload.get('commandType')
        if command not in (1118, 1153):
            return False
        value = payload.get('plateType' if command == 1118 else 'attType')
        timestamp = utc(timestamp)
        if not code(value) or timestamp is None:
            return False
        key = str(command)
        previous = self.reports.get(key)
        if previous and timestamp < previous['time']:
            return False
        report = {'code': value, 'source_command': command, 'time': timestamp,
                  'label': label(BEDS if command == 1118 else ACCESSORIES, value)}
        if previous and previous['code'] == value:
            for preserved_key in ('reply','reply_time','metadata','serial_present'):
                if preserved_key in previous:
                    report[preserved_key] = previous[preserved_key]
        if command == 1118 and 'reply' in payload:
            reply = payload['reply']
            if type(reply) in (int, bool) or reply is None:
                report['reply'] = reply
                report['reply_time'] = timestamp
        if command == 1153:
            # Preserve identifying originals only in private memory. Safe export keeps shape.
            if previous is None or previous['code'] != value:
                self.private_metadata = {}
            for metadata_key in ('version','modelName','sn'):
                if metadata_key in payload:
                    metadata_value = payload[metadata_key]
                    self.private_metadata[metadata_key] = metadata_value[:256] if isinstance(metadata_value, str) else metadata_value if number(metadata_value) is not None and abs(metadata_value) <= 10**12 else None
            report['metadata'] = {**report.get('metadata', {}), **{k: '<text omitted>' for k in self.private_metadata}}
            if 'sn' in payload:
                report['serial_present'] = bool(payload.get('sn')) and payload.get('sn') != '<text omitted>'
        self.reports[key] = report
        return previous is None or previous['code'] != value

    def identity(self):
        if not self.reports:
            return None
        report = max(self.reports.values(), key=lambda r: r['time'])
        return IDENTITIES[report['source_command']].get(report['code'],
                'unknown:%s:%s' % (report['source_command'], report['code']))

    def configuration(self):
        bed, accessory = self.reports.get('1118'), self.reports.get('1153')
        newest = max(self.reports.values(), key=lambda r: r['time']) if self.reports else None
        agreement = bed and accessory and IDENTITIES[1118].get(bed['code'], 'bed-unknown') == IDENTITIES[1153].get(accessory['code'], 'accessory-unknown')
        return {'bed': bed, 'accessory': accessory,
                'bed_present': (newest['code'] != 0) if newest and newest['code'] in IDENTITIES[newest['source_command']] else None,
                'consistency': 'Reports agree' if agreement else 'Awaiting matching report',
                'effective': newest['label'] if newest else None}


def state_description(pair):
    return STATUS.get(pair, 'Unknown (%s/%s)' % pair)


def transition(previous, pair, last_progress=None):
    parts = []
    if previous in OPERATIONS and previous != pair:
        parts.append(OPERATIONS[previous][0] + ' ended (status changed)')
    if previous in ((2, 4), (2, 3)) and pair == (0, 0):
        parts.append('Print completed' if last_progress == 10000 else 'Print ended (completion unconfirmed)')
    elif pair == (2, 4) and previous != pair:
        parts.append('Print resumed' if previous == (2, 3) else 'Print started')
    elif pair == (2, 3) and previous != pair:
        parts.append('Print paused')
    if pair in OPERATIONS and previous != pair:
        parts.append(OPERATIONS[pair][0] + ' started')
    elif pair in ((13, 0), (13, 1)) and previous != pair:
        parts.append('Post-maintenance state entered: ' + state_description(pair))
    return '; '.join(parts) or state_description(pair)
