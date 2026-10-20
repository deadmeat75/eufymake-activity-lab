import importlib.util
from pathlib import Path
import unittest
import sys, types
root=Path(__file__).parents[1]/'custom_components/eufymake_activity_lab'
pkg=types.ModuleType('lab_recorder');pkg.__path__=[str(root)];sys.modules[pkg.__name__]=pkg
from lab_recorder.recorder import Recorder

class Tests(unittest.TestCase):
    def message(self, recorder, state, step):
        return recorder.receive('message',{'commandType':1000,'status':{'state':state,'step':step},'secret_key':'DO-NOT-KEEP'})
    def test_changes_only_and_no_payload_storage(self):
        r=Recorder();r.receive('connected');self.assertTrue(self.message(r,5,7));self.assertFalse(self.message(r,5,7));self.message(r,0,0)
        self.assertEqual([e['step'] for e in r.events if e['kind']=='status'],[7,0]);self.assertNotIn('DO-NOT-KEEP',str(r.saved()))
    def test_survives_restart_and_retains_annotations(self):
        r=Recorder();self.message(r,5,7);eid=r.events[-1]['id'];r.annotate(eid,'Flash clean');r.label(5,7,'Automatic flash clean','confirmed')
        restarted=Recorder(r.saved());self.assertEqual(restarted.labels['5/7']['confidence'],'confirmed');self.assertEqual(restarted.events[-2]['note'],'Flash clean');self.assertNotEqual(r.session,restarted.session)
    def test_bounded_history_and_export(self):
        r=Recorder(limit=5)
        for step in range(12):self.message(r,2,step)
        self.assertEqual(len(r.events),5);self.assertEqual(r.dropped,8);self.assertEqual(len(r.snapshot(True)['events']),5)
    def test_pause_resume(self):
        r=Recorder();r.set_recording(False);self.message(r,2,1);self.assertEqual(r.current,{'state':2,'step':1});self.assertFalse(any(e['kind']=='status' for e in r.events));r.set_recording(True);self.message(r,2,1);self.assertEqual(r.events[-1]['kind'],'status')
    def test_reconnect_records_same_pair_again(self):
        r=Recorder();r.receive('connected');self.message(r,0,0);r.receive('disconnected');r.receive('connected');self.assertTrue(self.message(r,0,0))
    def test_invalid_status_and_oversized_input(self):
        r=Recorder();self.assertTrue(self.message(r,True,7));self.assertIsNone(r.current);self.assertFalse(any(e['kind']=='status' for e in r.events))
        with self.assertRaises(ValueError):r.label(2,1,'x'*121,'confirmed')
        with self.assertRaises(ValueError):r.annotate(r.events[0]['id'],'x'*1001)
    def test_missing_notes_rejected(self):
        with self.assertRaises(ValueError):Recorder().annotate('missing','a')
    def test_snapshot_is_detached(self):
        r=Recorder();snapshot=r.snapshot(True);snapshot['events'].clear();self.assertEqual(len(r.events),1)

if __name__=='__main__':unittest.main()
