from pathlib import Path
import sys, types
import unittest
pkg=types.ModuleType('lab_tools');pkg.__path__=[str(Path(__file__).parents[1]/'custom_components/eufymake_activity_lab')];sys.modules[pkg.__name__]=pkg
from lab_tools.recorder import Recorder


class ToolTests(unittest.TestCase):
    def test_sessions_export_only_the_selected_records_and_persist(self):
        r=Recorder();r.marker('Outside session');outside=r.events[-1]['id']
        r.recording_session('Latch test','Installed Mini Flatbed');sid=r.active_recording
        r.marker('Latch closed');r.recording_session(end=True,note='Detected correctly')
        r.marker('After session')
        exported=r.snapshot(True,recording_session=sid)
        self.assertTrue(all(e.get('recording_session')==sid for e in exported['events']))
        self.assertNotIn(outside,[e['id'] for e in exported['events']]);self.assertNotIn('live',exported);self.assertNotIn('decoded',exported)
        self.assertEqual(exported['recordings'][0]['note'],'Installed Mini Flatbed')
        self.assertEqual(exported['recordings'][0]['end_note'],'Detected correctly')
        restored=Recorder(r.saved());self.assertEqual(restored.recordings,r.recordings);self.assertIsNone(restored.active_recording)
        r.recording_session('Next session');restored=Recorder(r.saved());self.assertEqual(restored.active_recording,r.active_recording)
    def test_session_validation(self):
        r=Recorder()
        with self.assertRaises(ValueError):r.recording_session('')
        with self.assertRaises(ValueError):r.recording_session('ok',end='false')
        r.recording_session('A')
        with self.assertRaises(ValueError):r.recording_session('B')
        with self.assertRaises(ValueError):r.snapshot(True,recording_session='missing')
    def test_bookmark_preserves_id_and_revision_across_restart(self):
        r=Recorder();r.marker('Important');e=r.events[-1];eid=e['id'];rev=e['revision']
        r.bookmark(eid,True);self.assertEqual(e['id'],eid);self.assertEqual(e['revision'],rev+1)
        self.assertTrue(Recorder(r.saved()).events[-2]['bookmark'])
        r.bookmark(eid,False);self.assertFalse(e['bookmark'])
        with self.assertRaises(ValueError):r.bookmark('missing',True)
    def test_comparison_handles_arrays_missing_null_and_redaction(self):
        r=Recorder()
        a=r._add('unknown',fields={'a':1,'values':[2,3],'removed':None})
        b=r._add('unknown',fields={'a':1,'values':[2,4],'added':None})
        diff=r.compare(a['id'],b['id']);changes={x['field']:x for x in diff['changes']}
        self.assertEqual(changes['$.values[1]']['before'],3);self.assertEqual(changes['$.values[1]']['after'],4)
        self.assertFalse(changes['$.added']['before_present']);self.assertTrue(changes['$.added']['after_present'])
        self.assertNotIn('$.a',changes)
        with self.assertRaises(ValueError):r.compare(a['id'],a['id'])
    def test_old_event_ids_labels_notes_and_capture_settings_unchanged(self):
        saved={'events':[{'id':'old','revision':4,'time':'2026-10-20T00:00:00+00:00','kind':'marker','note':'Keep'}],'labels':{'2/2':{'label':'Ready','confidence':'confirmed'}},'limit':12000,'capture_telemetry':False}
        r=Recorder(saved);self.assertEqual(r.events[0],saved['events'][0]);self.assertEqual(r.labels,saved['labels']);self.assertFalse(r.capture_telemetry)

    def test_upgrade_backfills_retained_history_without_rewriting_events(self):
        events=[]
        for i,(cmd,fields) in enumerate([(1100,{'ink':{'leftInk':[6000]*6}}),(1000,{'status':{'state':2,'step':2}}),(1000,{'status':{'state':2,'step':4}}),(1001,{'progress':10000,'totalTime':1194,'time':17}),(1000,{'status':{'state':0,'step':0}})]):
            events.append({'id':str(i),'time':f'2026-10-27T19:24:{i:02}+00:00','kind':'telemetry','fields':{'commandType':cmd,**fields}})
        r=Recorder({'events':events,'interpretation':{'hardware':{},'clocks':{}}})
        self.assertEqual(r.snapshot()['decoded']['history']['prints'][-1]['elapsed_seconds'],1194)
        self.assertEqual(r.events[:5],events)
        self.assertIsNone(r.interpretation.insights.job)
        saved=r.saved();restored=Recorder(saved)
        self.assertEqual(len(restored.snapshot()['decoded']['history']['prints']),1)
