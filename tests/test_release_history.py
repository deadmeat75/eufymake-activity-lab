from pathlib import Path
import sys, types
pkg=types.ModuleType('lab_history');pkg.__path__=[str(Path(__file__).parents[1]/'custom_components/eufymake_activity_lab')];sys.modules[pkg.__name__]=pkg
from lab_history.insights import Insights
from datetime import datetime, timedelta, timezone
import json
import unittest


class HistoryTests(unittest.TestCase):
    def setUp(self):
        self.h = Insights()
        self.origin = datetime(2026,10,27,19,4,tzinfo=timezone.utc)
    def stamp(self, n):
        return (self.origin+timedelta(seconds=n)).isoformat()
    def send(self, n, cmd, **fields):
        self.h.observe({'commandType':cmd,**fields},self.stamp(n))
    def status(self, n, state, step):
        self.send(n,1000,status={'state':state,'step':step})
    def ink(self,n,level=6000,identity=None):
        ink={'leftInk':[level]*6,'expirationTimestamp':[1800460800]*6}
        if identity is not None:ink['sn']=[identity]*6
        self.send(n,1100,ink=ink)
    def begin(self):
        self.ink(0);self.status(1,2,2);self.send(2,1140);self.status(3,2,4)
    def test_completion_preserves_last_metrics_and_does_not_complete_at_100_percent(self):
        self.begin()
        self.send(1194,1001,progress=10000,time=17,totalTime=1194)
        self.assertEqual(self.h.public()['prints'],[])
        self.status(1205,0,0)
        record=self.h.public()['prints'][-1]
        self.assertTrue(record['completion_confirmed'])
        self.assertEqual(record['elapsed_seconds'],1194)
        self.assertEqual(record['remaining_seconds'],17)
        self.send(1206,1001,totalTime=0,progress=10000,time=0)
        self.assertEqual(self.h.public()['prints'][-1]['elapsed_seconds'],1194)
        self.assertEqual(record['start_method'],'Unknown')
        self.assertIn('Unverified',record['experimental_start_signal']['meaning'])
    def test_end_without_fresh_100_percent_is_unconfirmed(self):
        self.begin();self.send(4,1001,progress=9000);self.status(5,0,0)
        self.assertFalse(self.h.public()['prints'][-1]['completion_confirmed'])
        self.status(6,2,4);self.send(7,1001,progress=10000);self.status(200,0,0)
        self.assertFalse(self.h.public()['prints'][-1]['completion_confirmed'])
    def test_reconnect_does_not_invent_completion_or_maintenance_finish(self):
        self.begin();self.send(4,1001,progress=10000)
        self.h.connection_event(False,self.stamp(5));self.h.connection_event(True,self.stamp(6));self.status(7,0,0)
        self.assertEqual(self.h.public()['prints'],[])
        self.status(8,5,7);self.h.connection_event(False,self.stamp(9));self.status(10,0,0)
        self.assertEqual(self.h.public()['maintenance'],[])
    def test_pause_resume_does_not_make_two_jobs(self):
        self.begin();start=self.h.job['start'];self.status(4,2,3);self.status(5,2,4)
        self.send(6,1001,progress=10000,totalTime=3);self.status(7,0,0)
        self.assertEqual(len(self.h.public()['prints']),1)
        self.assertEqual(self.h.public()['prints'][0]['start'],start)
    def test_quantities_are_unitless_and_maintenance_does_not_reuse_job_quantities(self):
        self.begin();self.send(4,1068,ink_quantity=[1,1,1,1,0.53508,0.5],print_quantity=3.83,pump_quantity=1.2)
        self.send(5,1001,progress=10000,totalTime=1194);self.status(6,0,0)
        q=self.h.public()['prints'][-1]['reported_quantities']
        self.assertAlmostEqual(q['six_channel_total'],5.03508)
        self.assertEqual(q['units'],'Unverified')
        self.status(7,5,7);self.status(36.3,0,0)
        m=self.h.public()['maintenance'][-1]
        self.assertEqual(m['duration_seconds'],29.3)
        self.assertNotIn('reported_quantities',m)
    def test_all_maintenance_pairs_exclude_persistent_post_states(self):
        for index,pair in enumerate(((5,7),(5,9),(5,10),(5,3))):
            self.status(index*100,pair[0],pair[1]);self.status(index*100+31,13,index%2)
        self.status(10000,13,1)
        self.assertEqual(len(self.h.public()['maintenance']),4)
        self.assertTrue(all(m['duration_seconds']==31 for m in self.h.public()['maintenance']))
    def test_inventory_estimate_and_increases_or_gaps(self):
        self.begin();self.ink(20,5900);self.send(21,1001,progress=10000);self.status(22,0,0)
        u=self.h.public()['prints'][-1]['usage'];self.assertEqual(u['total_estimated_ml'],6)
        self.status(23,2,2);self.status(24,2,4);self.ink(25,6000);self.send(26,1001,progress=10000);self.status(27,0,0)
        self.assertNotIn('total_estimated_ml',self.h.public()['prints'][-1]['usage'])
        self.status(28,2,2);self.status(29,2,4);self.ink(200,5800);self.send(201,1001,progress=10000);self.status(202,0,0)
        self.assertNotIn('total_estimated_ml',self.h.public()['prints'][-1]['usage'])
    def test_cartridge_changes_need_identity_and_never_publish_serials_or_hashes(self):
        self.ink(0,6000,'PRIVATE-OLD');self.ink(1,5000,'PRIVATE-OLD');self.ink(2,9000,'PRIVATE-NEW');self.ink(3,5000,'PRIVATE-OLD')
        self.assertEqual(len(self.h.public()['cartridge_changes']),12)
        saved=json.dumps(self.h.saved());public=json.dumps(self.h.public())
        self.assertNotIn('PRIVATE-',saved);self.assertNotIn('salt',public);self.assertNotIn('identities',public)
        restored=Insights(self.h.saved());restored.observe({'commandType':1100,'ink':{'leftInk':[5000]*6,'sn':['PRIVATE-OLD']*6}},self.stamp(4))
        self.assertEqual(len(restored.public()['cartridge_changes']),12)
        self.ink(5,10000);self.assertEqual(len(self.h.public()['cartridge_changes']),12)
    def test_sampling_bounds_and_detached_snapshot(self):
        for i in range(1000):self.ink(i,6000-i)
        self.assertEqual(len(self.h.public()['ink_history']),4)
        for i in range(1001,230000,300):self.ink(i,5000)
        self.assertEqual(len(self.h.public()['ink_history']),720)
        self.h.public()['ink_history'].clear();self.assertEqual(len(self.h.public()['ink_history']),720)
    def test_ordering_and_malformed_numeric_values(self):
        self.begin();self.send(10,1001,progress=1700,time=678,totalTime=187)
        self.send(9,1001,progress=10000);self.send(11,1001,progress=True,time=float('nan'),totalTime=-1)
        self.assertEqual(self.h.job['progress'],1700);self.assertEqual(self.h.job['remaining_seconds'],678)
        self.assertEqual(self.h.job['elapsed_seconds'],187)
        self.send(12,1068,ink_quantity=[float('inf')]*6,pump_quantity=-1)
        self.assertNotIn('reported_quantities',self.h.job)
        for value in (None,[],{'commandType':True},{'commandType':1000,'status':[]}):self.h.observe(value,self.stamp(13))
    def test_connection_durations_and_restart_summaries(self):
        self.h.connection_event(True,self.stamp(0));self.h.connection_event(False,self.stamp(30));self.h.connection_event(False,self.stamp(31));self.h.connection_event(True,self.stamp(120))
        conn=self.h.public()['connections'];self.assertEqual(len(conn),3);self.assertEqual(conn[-1]['previous_duration_seconds'],90)
        restored=Insights(self.h.saved());self.assertEqual(restored.public(),self.h.public());self.assertIsNone(restored.job)

    def test_invalid_progress_cannot_refresh_old_completion_and_missing_endpoint_is_not_zero_usage(self):
        self.begin();self.send(4,1001,progress=10000)
        self.send(200,1001,progress=True);self.status(201,0,0)
        self.assertFalse(self.h.public()['prints'][-1]['completion_confirmed'])
        self.assertNotIn('total_estimated_ml',self.h.public()['prints'][-1]['usage'])
