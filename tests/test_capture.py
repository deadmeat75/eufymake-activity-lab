import importlib.util
import json
from pathlib import Path
import sys
import threading
import types
import unittest
from unittest.mock import patch
root=Path(__file__).parents[1]/'custom_components/eufymake_activity_lab'
pkg=types.ModuleType('lab_capture');pkg.__path__=[str(root)];sys.modules[pkg.__name__]=pkg
from lab_capture.recorder import Recorder,safe_fields
from lab_capture.cloud import CloudClient
from lab_capture.protocol import build_app_frame

class Tests(unittest.TestCase):
    def test_telemetry_deduplicated_and_throttled(self):
        r=Recorder()
        with patch('lab_capture.recorder.time.monotonic',return_value=100):
            self.assertTrue(r.receive('message',{'commandType':1001,'progress':5000,'time':60}))
            self.assertFalse(r.receive('message',{'commandType':1001,'progress':5000,'time':60}))
            self.assertFalse(r.receive('message',{'commandType':1001,'progress':5100,'time':59}))
        with patch('lab_capture.recorder.time.monotonic',return_value=106):
            self.assertTrue(r.receive('message',{'commandType':1001,'progress':5100,'time':59}))
        self.assertEqual(r.live['1001']['fields']['progress'],5100)
    def test_unknown_numeric_data_and_redaction(self):
        r=Recorder();r.receive('message',{'commandType':9000,'temperature':31.5,'password':'secret','user_id':123,'name':'private title','nested':{'secret_key':'00'*32,'samples':[1,2,3]}})
        event=r.events[-1];self.assertEqual(event['kind'],'unknown');self.assertEqual(event['fields']['temperature'],31.5)
        export=json.dumps(r.snapshot(True));self.assertNotIn('private title',export);self.assertNotIn('secret_key',export);self.assertNotIn('"user_id"',export)
    def test_diagnostics_do_not_disconnect(self):
        r=Recorder();r.receive('connected');r.receive('diagnostic',{'reason':'fragmented_frame'});self.assertTrue(r.connected);self.assertEqual(r.diagnostics['fragmented_frame'],1)
    def test_telemetry_does_not_finish_status_duration(self):
        r=Recorder();r.receive('message',{'commandType':1000,'status':{'state':2,'step':1}})
        eid=r.events[-1]['id'];r.receive('message',{'commandType':1001,'progress':100,'time':60})
        event=next(e for e in r.events if e['id']==eid);self.assertNotIn('duration_seconds',event)
        r.receive('message',{'commandType':1000,'status':{'state':2,'step':2}});self.assertIn('duration_seconds',event)
    def test_capture_settings_survive_restart(self):
        r=Recorder();r.settings(False,False);r.receive('message',{'commandType':9000,'value':1});self.assertEqual(len(r.events),1)
        restored=Recorder(r.saved());self.assertFalse(restored.capture_unknown);self.assertFalse(restored.capture_telemetry)
    def test_marker_and_bounded_sanitizer(self):
        r=Recorder();r.marker('Pressed Start');self.assertEqual(r.events[-1]['note'],'Pressed Start')
        self.assertLessEqual(len(safe_fields({str(i):i for i in range(1000)})),64)
        self.assertEqual(safe_fields({'value':float('nan')})['value'],None)
    def test_transport_captures_unknown_commands(self):
        c=CloudClient.__new__(CloudClient);c.stopping=threading.Event();c.key=bytes.fromhex('11'*32);events=[];c.on_event=lambda *e:events.append(e)
        wire=build_app_frame(c.key,json.dumps({'commandType':9000,'temperature':32}).encode())
        c._on_message(None,None,types.SimpleNamespace(payload=wire));self.assertEqual(events[-1][1]['commandType'],9000)
        bad=wire[:-1]+bytes([wire[-1]^1]);c._on_message(None,None,types.SimpleNamespace(payload=bad));self.assertEqual(events[-1][1]['reason'],'checksum_failed')
        fragment=bytearray(wire);fragment[9]=0xC1;checksum=0
        for b in fragment[:-1]:checksum^=b
        fragment[-1]=checksum;c._on_message(None,None,types.SimpleNamespace(payload=bytes(fragment)));self.assertEqual(events[-1][1]['reason'],'fragmented_frame')

if __name__=='__main__':unittest.main()
