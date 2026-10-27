import asyncio
import importlib.util
from pathlib import Path
import sys
import types
import tempfile
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).parent))
import ha_stubs

def module(name, **fields):
    m=types.ModuleType(name);m.__path__=[];m.__dict__.update(fields);sys.modules[name]=m;return m
module('homeassistant.components.frontend', async_remove_panel=lambda *a:None)
module('homeassistant.components.panel_custom', async_register_panel=None)
module('homeassistant.components.http', StaticPathConfig=lambda *a,**kw:None)
module('homeassistant.components.websocket_api',websocket_command=lambda schema:lambda f:f,async_response=lambda f:f)
module('homeassistant.const',EVENT_HOMEASSISTANT_STOP='stop')
module('homeassistant.exceptions',ConfigEntryAuthFailed=type('AuthError',(Exception,),{}),ConfigEntryNotReady=type('NotReady',(Exception,),{}))
root=Path(__file__).parents[1]/'custom_components/eufymake_activity_lab'
spec=importlib.util.spec_from_file_location('lab_runtime',root/'__init__.py',submodule_search_locations=[str(root)])
runtime=importlib.util.module_from_spec(spec);sys.modules[spec.name]=runtime;spec.loader.exec_module(runtime)

class Cloud:
    def __init__(self,data,on_event):self.event=on_event;self.stopped=False
    def start(self):self.event('connected',None)
    def stop(self):self.stopped=True
    def query(self):pass
class Conn:
    def __init__(self,admin):self.user=types.SimpleNamespace(is_admin=admin);self.result=None;self.error=None
    def send_result(self,id,result):self.result=result
    def send_error(self,id,code,message):self.error=code

class Tests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        ha_stubs.Store.saved.clear();self.temp=tempfile.TemporaryDirectory();self.hass=ha_stubs.FakeHass();self.hass.config=types.SimpleNamespace(path=lambda *parts:str(Path(self.temp.name).joinpath(*parts)));self.hass.async_create_background_task=lambda coro,*a,**k:asyncio.create_task(coro)
        self.entry=types.SimpleNamespace(entry_id='test',data={},async_start_reauth=lambda h:None)
        self.p=patch.object(runtime,'CloudClient',Cloud);self.p.start();self.r=runtime.Runtime(self.hass,self.entry);await self.r.start();await asyncio.sleep(0)
        self.hass.data[runtime.DOMAIN]={'test':self.r}
    async def asyncTearDown(self):await self.r.stop();self.p.stop();self.temp.cleanup()
    async def test_admin_only(self):
        c=Conn(False);await runtime.websocket_action(self.hass,c,{'id':1,'entry_id':'test','action':'read','data':{}});self.assertEqual(c.error,'unauthorized')
    async def test_annotation_is_saved(self):
        self.r.receive('message',{'commandType':1000,'status':{'state':5,'step':7}})
        eid=self.r.recorder.events[-1]['id'];c=Conn(True)
        await runtime.websocket_action(self.hass,c,{'id':1,'entry_id':'test','action':'note','data':{'id':eid,'note':'Flash clean'}})
        self.assertEqual(c.result['events'][-1]['note'],'Flash clean');self.assertEqual((await self.r.store.async_load())['events'][-1]['note'],'Flash clean')
    async def test_clear_requires_confirmation(self):
        c=Conn(True);await runtime.websocket_action(self.hass,c,{'id':1,'entry_id':'test','action':'clear','data':{}});self.assertEqual(c.error,'invalid_request');self.assertGreater(len(self.r.recorder.events),0)
    async def test_shutdown_flushes_and_ignores_late_messages(self):
        self.r.receive('message',{'commandType':1000,'status':{'state':8,'step':0}});await self.r.stop();count=len(self.r.recorder.events)
        self.r.receive('message',{'commandType':1000,'status':{'state':2,'step':4}});self.assertEqual(len(self.r.recorder.events),count);self.assertTrue(self.r.client.stopped)
        saved=await self.r.store.async_load();self.assertTrue(any(e.get('state')==8 for e in saved['events']))
    async def test_invalid_label_rejected(self):
        c=Conn(True);await runtime.websocket_action(self.hass,c,{'id':1,'entry_id':'test','action':'label','data':{'state':'bad','step':2,'label':'Wait','confidence':'confirmed'}});self.assertEqual(c.error,'invalid_request')

    async def test_session_bookmark_compare_and_scoped_export_are_saved(self):
        c=Conn(True)
        async def action(name,data):
            c.error=None
            await runtime.websocket_action(self.hass,c,{'id':1,'entry_id':'test','action':name,'data':data})
            self.assertIsNone(c.error)
            return c.result
        await action('session',{'name':'Bed test','note':'Safe observation'})
        sid=self.r.recorder.active_recording
        a=self.r.recorder._add('unknown',fields={'plateType':0})
        b=self.r.recorder._add('unknown',fields={'plateType':2})
        await action('bookmark',{'id':a['id'],'enabled':True})
        self.assertTrue(next(e for e in (await self.r.store.async_load())['events'] if e['id']==a['id'])['bookmark'])
        comparison=await action('compare',{'first':a['id'],'second':b['id']})
        self.assertEqual(comparison['changes'][0]['field'],'$.plateType')
        await action('session',{'end':True})
        exported=await action('export',{'recording_session':sid})
        self.assertTrue(all(e.get('recording_session')==sid for e in exported['events']))
        self.assertNotIn('decoded',exported)
