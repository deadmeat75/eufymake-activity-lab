"""Private, independent Home Assistant activity recorder."""
import asyncio
import logging
import sqlite3
from pathlib import Path
import probatio as vol
from homeassistant.components import frontend, panel_custom, websocket_api
from homeassistant.components.http import StaticPathConfig
from homeassistant.const import EVENT_HOMEASSISTANT_STOP
from homeassistant.core import callback
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from .storage import Journal
from .cloud import CloudClient, CloudAuthError, CloudError
from .const import DOMAIN, MAX_RECORDS
from .recorder import Recorder

LOGGER = logging.getLogger(__name__)


class Runtime:
    def __init__(self, hass, entry):
        self.hass = hass
        self.entry = entry
        self.store = Journal(hass, entry.entry_id)
        self.save_lock = asyncio.Lock()
        self.recorder = None
        self.client = CloudClient(dict(entry.data), self.cloud_event)
        self.closed = False
        self.query_task = None
        self.dirty = False
        self.remove_stop = None
        self.reauth_started = False
        self.path = 'eufymake-activity-' + entry.entry_id

    def cloud_event(self, kind, payload):
        self.hass.add_job(self.receive, kind, payload)

    @callback
    def receive(self, kind, payload):
        if self.closed:
            return
        if self.recorder.receive(kind, payload):
            self.dirty = True
        if kind == 'auth_failed' and not self.reauth_started:
            self.reauth_started = True
            self.entry.async_start_reauth(self.hass)

    async def persist(self):
        async with self.save_lock:
            await self.store.async_save(self.recorder.saved())

    async def start(self):
        self.recorder = Recorder(await self.store.async_load(), MAX_RECORDS)
        await self.persist()
        await self.hass.async_add_executor_job(self.client.start)
        self.query_task = self.hass.async_create_background_task(self.query_loop(), "EufyMake Activity Lab persistence", eager_start=False)

    async def query_loop(self):
        try:
            ticks = 0
            while not self.closed:
                await asyncio.sleep(2)
                if self.dirty:
                    self.dirty = False
                    try:
                        await self.persist()
                    except (OSError, sqlite3.Error):
                        self.dirty = True
                        LOGGER.error("Activity Lab could not save history; check storage space and permissions")
                ticks += 1
                if ticks % 15 == 0:
                    self.dirty = True
                    try:
                        await self.hass.async_add_executor_job(self.client.query)
                    except OSError:
                        LOGGER.warning("Activity Lab telemetry query failed; retrying next interval")
        except asyncio.CancelledError:
            pass

    async def stop(self):
        if self.closed:
            return
        self.closed = True
        if self.remove_stop:
            self.remove_stop()
            self.remove_stop = None
        if self.query_task:
            self.query_task.cancel()
            await self.query_task
        await self.hass.async_add_executor_job(self.client.stop)
        if self.recorder:
            self.recorder.receive('disconnected')
            await self.persist()


@websocket_api.websocket_command({vol.Required('type'): 'eufymake_activity_lab/action',
    vol.Required('entry_id'): str, vol.Optional('action', default='read'): str,
    vol.Optional('data', default={}): dict})
@websocket_api.async_response
async def websocket_action(hass, connection, msg):
    if not connection.user or not connection.user.is_admin:
        connection.send_error(msg['id'], 'unauthorized', 'Administrator access required')
        return
    runtime = hass.data.get(DOMAIN, {}).get(msg['entry_id'])
    if not runtime or runtime.closed:
        connection.send_error(msg['id'], 'not_loaded', 'Activity Lab is not loaded')
        return
    recorder = runtime.recorder
    data, action = msg['data'], msg['action']
    try:
        if action == 'marker':
            recorder.marker(data['note'])
        elif action == 'settings':
            recorder.settings(data['telemetry'], data['unknown'], data.get('retention'))
        elif action == 'note':
            recorder.annotate(data['id'], data['note'])
        elif action == 'label':
            recorder.label(data['state'], data['step'], data['label'], data['confidence'])
        elif action == 'recording':
            recorder.set_recording(data['enabled'])
        elif action == 'clear':
            if data.get('confirm') != 'CLEAR':
                raise ValueError('Clear confirmation missing')
            recorder.events.clear()
            recorder.dropped = 0
            recorder.last_status = None
            recorder.active_status = None
            recorder.last_data.clear()
            recorder._add('history', detail='History cleared by administrator')
        elif action not in ('read', 'export'):
            raise ValueError('Unknown action')
        if action not in ('read', 'export'):
            await runtime.persist()
        connection.send_result(msg['id'], recorder.snapshot(export=action == 'export'))
    except (ValueError, KeyError, TypeError) as error:
        connection.send_error(msg['id'], 'invalid_request', str(error))


async def async_setup(hass, config):
    hass.data.setdefault(DOMAIN, {})
    websocket_api.async_register_command(hass, websocket_action)
    await hass.http.async_register_static_paths([StaticPathConfig(
        '/eufymake_activity_lab/panel.js', str(Path(__file__).parent / 'www/panel.js'), cache_headers=False)])
    return True


async def async_setup_entry(hass, entry):
    runtime = Runtime(hass, entry)
    try:
        await runtime.start()
    except CloudAuthError:
        await runtime.stop()
        raise ConfigEntryAuthFailed('Reimport your current Studio files') from None
    except (CloudError, OSError):
        await runtime.stop()
        raise ConfigEntryNotReady('Activity Lab could not connect to the cloud') from None
    hass.data[DOMAIN][entry.entry_id] = runtime
    try:
        await panel_custom.async_register_panel(hass, frontend_url_path=runtime.path,
            webcomponent_name='eufymake-activity-lab', sidebar_title='E1 Lab · ' + entry.data['serial'][-6:],
            sidebar_icon='mdi:timeline-clock-outline', module_url='/eufymake_activity_lab/panel.js?v=0.2.0',
            embed_iframe=False, require_admin=True, config={'entry_id': entry.entry_id})
    except Exception:
        hass.data[DOMAIN].pop(entry.entry_id, None)
        await runtime.stop()
        raise

    async def stop(event):
        await runtime.stop()
    runtime.remove_stop = hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, stop)
    return True


async def async_unload_entry(hass, entry):
    runtime = hass.data[DOMAIN].pop(entry.entry_id, None)
    if runtime:
        frontend.async_remove_panel(hass, runtime.path)
        await runtime.stop()
    return True


async def async_remove_entry(hass, entry):
    await Journal(hass, entry.entry_id).async_remove()
