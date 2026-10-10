import asyncio
import importlib.util
from pathlib import Path
import tempfile
import types
import unittest
spec=importlib.util.spec_from_file_location('journal',Path(__file__).parents[1]/'custom_components/eufymake_activity_lab/storage.py')
journal=importlib.util.module_from_spec(spec);spec.loader.exec_module(journal)

class Tests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp=tempfile.TemporaryDirectory()
        async def executor(fn,*a):return await asyncio.to_thread(fn,*a)
        self.hass=types.SimpleNamespace(config=types.SimpleNamespace(path=lambda *p:str(Path(self.temp.name).joinpath(*p))),async_add_executor_job=executor)
        self.store=journal.Journal(self.hass,'test')
    async def asyncTearDown(self):self.temp.cleanup()
    async def test_incremental_update_delete_and_restart(self):
        self.assertEqual((await self.store.async_load())['events'],[])
        await self.store.async_save({'events':[{'id':'a','revision':1,'note':'before'},{'id':'b','revision':1}],'labels':{'2/1':'test'}})
        await self.store.async_save({'events':[{'id':'a','revision':2,'note':'after'}],'labels':{}})
        restored=journal.Journal(self.hass,'test');saved=await restored.async_load()
        self.assertEqual(saved['events'],[{'id':'a','revision':2,'note':'after'}])
        await restored.async_remove();self.assertFalse(restored.path.exists())
    async def test_invalid_entry_id(self):
        with self.assertRaises(ValueError):journal.Journal(self.hass,'../escape')
