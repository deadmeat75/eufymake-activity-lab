"""Physical swap fixtures, ordered history and observational interpretation."""
import json
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import patch
root=Path(__file__).parents[1]/'custom_components/eufymake_activity_lab'
pkg=types.ModuleType('lab_verified');pkg.__path__=[str(root)];sys.modules[pkg.__name__]=pkg
from lab_verified.recorder import Recorder
from lab_verified.telemetry import OPERATIONS

FIXTURE=json.loads((Path(__file__).parent/'fixtures/verified_october.json').read_text())

class InterpretationTests(unittest.TestCase):
    def test_physical_swaps_record_both_raw_commands_but_one_installation(self):
        r=Recorder()
        for timestamp,payload in FIXTURE['accessory_events']:
            r.receive('message',payload,observed_at=timestamp)
        installs=[e for e in r.events if e.get('detail','').endswith(' installed')]
        self.assertEqual([e['detail'] for e in installs],['Standard Flatbed installed','Rotary installed','Mini Flatbed installed'])
        self.assertTrue(any(e.get('fields',{}).get('reply')==1 for e in r.events))
        self.assertEqual(r.snapshot()['decoded']['hardware']['bed']['label'],'Mini Flatbed')
        self.assertEqual(r.snapshot()['decoded']['hardware']['accessory']['code'],1)
        restored=Recorder(r.saved())
        before=len(restored.events)
        restored.receive('connected')
        restored.receive('message',{'commandType':1153,'attType':1},observed_at='2026-10-20T19:00:00Z')
        self.assertFalse(any('installed' in e.get('detail','') for e in restored.events[before:]))

    def test_duplicate_and_out_of_order_messages_do_not_revert_current_hardware(self):
        r=Recorder()
        payload={'commandType':1118,'plateType':2,'reply':0}
        r.receive('message',payload,observed_at='2026-10-20T18:41:21Z')
        size=len(r.events)
        self.assertFalse(r.receive('message',payload,observed_at='2026-10-20T18:41:21Z'))
        self.assertEqual(len(r.events),size)
        r.receive('message',{'commandType':1118,'plateType':0},observed_at='2026-10-20T18:40:48Z')
        self.assertEqual(r.snapshot()['decoded']['hardware']['bed']['code'],2)
        late=[e for e in r.events if e.get('historical')]
        self.assertEqual(len(late),1)
        self.assertEqual([e['time'] for e in r.events],sorted(e['time'] for e in r.events))

    def test_progress_and_state_transitions_do_not_report_early_completion(self):
        r=Recorder();send=lambda p,t:r.receive('message',p,observed_at=t)
        send({'commandType':1000,'status':{'state':2,'step':4}},'2026-10-20T18:00:00Z')
        send({'commandType':1001,'progress':1700,'time':678,'totalTime':187},'2026-10-20T18:00:01Z')
        self.assertEqual(r.snapshot()['decoded']['readings']['1001']['fields']['time'],678)
        send({'commandType':1001,'progress':10000,'time':17},'2026-10-20T18:01:00Z')
        self.assertFalse(any('completed' in e.get('detail','') for e in r.events))
        send({'commandType':1000,'status':{'state':0,'step':0}},'2026-10-20T18:01:17Z')
        self.assertIn('Print completed',[e for e in r.events if e['kind']=='status'][-1]['detail'])
        send({'commandType':1001,'progress':10000,'time':17},'2026-10-20T18:01:18Z')
        self.assertNotIn('1001',r.snapshot()['decoded']['readings'])

    def test_each_maintenance_source_and_post_maintenance_state(self):
        r=Recorder()
        second=0
        for pair,(_,command) in OPERATIONS.items():
            r.receive('message',{'commandType':1000,'status':{'state':pair[0],'step':pair[1]}},observed_at=f'2026-10-20T18:{second:02}:00Z')
            r.receive('message',{'commandType':command,'progress':37},observed_at=f'2026-10-20T18:{second:02}:01Z')
            activity=r.snapshot()['decoded']['readings']['activity']
            self.assertEqual(activity['progress'],37);self.assertEqual(activity['source_command'],command)
            second+=1
        r.receive('message',{'commandType':1000,'status':{'state':13,'step':0}},observed_at='2026-10-20T18:10:00Z')
        self.assertNotIn('activity',r.snapshot()['decoded']['readings'])
        r.receive('message',{'commandType':1000,'status':{'state':13,'step':0}},observed_at='2026-10-20T20:10:00Z')
        self.assertNotIn('activity',r.snapshot()['decoded']['readings'])
        self.assertFalse('error' in r.snapshot()['decoded']['status'].lower())

    def test_private_metadata_and_malformed_messages(self):
        r=Recorder()
        r.receive('message',{'commandType':1153,'attType':4,'version':'1.0','modelName':'Rotary','sn':12345678,'token':'SECRET'},observed_at='2026-10-20T18:00:00Z')
        exported=json.dumps(r.snapshot(True))
        self.assertNotIn('12345678',exported);self.assertNotIn('SECRET',exported)
        self.assertEqual(r.interpretation.hardware.private_metadata['sn'],12345678)
        for payload in (None,[],{}, {'commandType':[]}, {'commandType':1000,'status':None}):
            r.receive('message',payload)
        r.receive('diagnostic',None)
        r.receive('message',{'commandType':1000,'status':{'state':2,'step':4}})
        r.receive('message',{'commandType':1001,'progress':'PRIVATE-UNEXPECTED','time':'PRIVATE-UNEXPECTED','totalTime':'PRIVATE-UNEXPECTED'})
        self.assertNotIn('PRIVATE-UNEXPECTED',json.dumps(r.snapshot(True)))

    def test_state_residence_uses_event_times_not_processing_times(self):
        r=Recorder()
        r.receive('message',{'commandType':1000,'status':{'state':5,'step':7}},observed_at='2026-10-20T18:00:00Z')
        r.receive('message',{'commandType':1000,'status':{'state':0,'step':0}},observed_at='2026-10-20T18:00:31Z')
        first=next(e for e in r.events if e['kind']=='status')
        self.assertEqual(first['duration_seconds'],31)
        ids=[e['id'] for e in r.events]
        saved=r.saved();self.assertEqual([e['id'] for e in saved['events']],ids)

    def test_reconnect_does_not_restore_old_active_progress(self):
        r=Recorder()
        r.receive('message',{'commandType':1000,'status':{'state':2,'step':4}},observed_at='2026-10-20T18:00:00Z')
        r.receive('message',{'commandType':1001,'progress':10000,'time':17},observed_at='2026-10-20T18:00:01Z')
        r.receive('disconnected',observed_at='2026-10-20T18:00:02Z')
        r.receive('connected',observed_at='2026-10-20T18:00:03Z')
        self.assertIsNone(r.current)
        self.assertNotIn('1001',r.snapshot()['decoded']['readings'])
        r.receive('message',{'commandType':1000,'status':{'state':0,'step':0}},observed_at='2026-10-20T18:00:04Z')
        self.assertNotIn('Print completed',[e for e in r.events if e['kind']=='status'][-1]['detail'])
