import importlib.util
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).parent))
import ha_stubs
ha_stubs.Flow.async_show_menu=lambda self,**fields:{'type':'menu',**fields}
root=Path(__file__).parents[1]/'custom_components/eufymake_activity_lab'
pkg=types.ModuleType('lab_flow');pkg.__path__=[str(root)];sys.modules[pkg.__name__]=pkg
from lab_flow import config_flow

class Tests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.entry=types.SimpleNamespace(entry_id='normal',title='E1',data={'user_id':'TEST','email':'test@example.invalid','region':'US','serial':'TESTSERIAL','secret_key':'00'*32,'ca_pem':'fixture-only','extra':'do not copy'})
        self.flow=config_flow.ActivityLabConfigFlow();self.flow.hass=types.SimpleNamespace(config_entries=types.SimpleNamespace(async_entries=lambda domain:[self.entry]));self.flow.context={}
        async def executor(fn,*args):return fn(*args)
        self.flow.hass.async_add_executor_job=executor
    async def test_existing_monitor_menu(self):
        result=await self.flow.async_step_user();self.assertEqual(result['type'],'menu');self.assertEqual(result['menu_options'],['existing','files'])
    async def test_existing_credentials_only_and_cloud_validation(self):
        with patch.object(config_flow,'_validate_cloud') as validate:
            result=await self.flow.async_step_existing({'monitor':'normal'})
        self.assertEqual(result['type'],'create_entry');self.assertNotIn('extra',result['data']);validate.assert_called_once()
    async def test_missing_selected_entry(self):
        result=await self.flow.async_step_existing({'monitor':'missing'});self.assertEqual(result['errors']['base'],'invalid_selection')
    async def test_no_existing_monitor_uses_files(self):
        self.flow.hass.config_entries.async_entries=lambda domain:[]
        result=await self.flow.async_step_user();self.assertEqual(result['step_id'],'files')
