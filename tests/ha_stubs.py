"""Small HA API doubles for boundary tests; not a substitute for running HA Core."""
import asyncio
import sys
import types


def module(name, **fields):
    item = types.ModuleType(name)
    item.__path__ = []
    item.__dict__.update(fields)
    sys.modules[name] = item
    return item


class AbortFlow(Exception):
    pass


class Flow:
    def __init_subclass__(cls, **kwargs):
        pass
    def async_show_form(self, **fields):
        return {'type':'form', **fields}
    def async_create_entry(self, **fields):
        return {'type':'create_entry', **fields}
    async def async_set_unique_id(self, value):
        self.unique_id = value
    def _abort_if_unique_id_configured(self):
        if getattr(self,'duplicate',False):
            raise AbortFlow('already_configured')
    def _get_reauth_entry(self):
        return self.reauth_entry
    def async_update_reload_and_abort(self, entry, **fields):
        return {'type':'abort','reason':'reauth_successful','entry':entry,**fields}


class Selector:
    def __init__(self, config):
        self.config = config
    def __call__(self, value):
        return value


class Coordinator:
    def __init__(self,hass,logger,**kwargs):
        self.hass=hass
        self.data=None
    def async_set_updated_data(self,data):
        self.data=data
    async def async_config_entry_first_refresh(self):
        self.data=await self._async_update_data()
    async def async_shutdown(self):
        pass


class CoordinatorEntity:
    def __init__(self,coordinator):
        self.coordinator=coordinator


class Store:
    saved={}
    def __init__(self,hass,version,key):
        self.key=key
        self.pending=None
    async def async_load(self):
        return self.saved.get(self.key)
    async def async_save(self,data):
        self.saved[self.key]=dict(data)
    def async_delay_save(self,callback,delay):
        self.pending=callback
    async def async_remove(self):
        self.saved.pop(self.key,None)


class FakeHass:
    def __init__(self):
        self.loop=asyncio.get_running_loop()
        self.data={}
    async def async_add_executor_job(self,func,*args):
        return await asyncio.to_thread(func,*args)
    def add_job(self,func,*args):
        self.loop.call_soon_threadsafe(func,*args)


module('homeassistant')
module('homeassistant.config_entries', ConfigFlow=Flow, SOURCE_REAUTH='reauth')
module('homeassistant.components')
module('homeassistant.components.file_upload',process_uploaded_file=lambda *args:None)
module('homeassistant.helpers')
module('homeassistant.helpers.selector',FileSelector=Selector,SelectSelector=Selector)
module('homeassistant.helpers.event',async_track_time_interval=lambda *args:lambda:None)
module('homeassistant.helpers.storage',Store=Store)
module('homeassistant.helpers.update_coordinator',DataUpdateCoordinator=Coordinator,CoordinatorEntity=CoordinatorEntity)
module('homeassistant.helpers.device_registry',DeviceInfo=lambda **fields:fields)
module('homeassistant.components.sensor',SensorEntity=type('SensorEntity',(),{}),SensorDeviceClass=types.SimpleNamespace(DURATION='duration'))
module('homeassistant.components.date',DateEntity=type('DateEntity',(),{}))
module('homeassistant.core',callback=lambda function:function)
module('homeassistant.util')
import datetime
module('homeassistant.util.dt',now=lambda:datetime.datetime(2026,10,8,tzinfo=datetime.timezone.utc))
