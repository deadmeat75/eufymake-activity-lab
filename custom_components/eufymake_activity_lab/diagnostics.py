"""Capture health only: no credentials, annotations or decoded field values."""
from .const import DOMAIN, VERSION


async def async_get_config_entry_diagnostics(hass, entry):
    runtime = hass.data.get(DOMAIN, {}).get(entry.entry_id)
    if not runtime:
        return {'version': VERSION, 'loaded': False}
    recorder = runtime.recorder
    return {'version': VERSION, 'loaded': True, 'connected': recorder.connected,
            'recording': recorder.recording, 'retained': len(recorder.events),
            'dropped': recorder.dropped, 'limit': recorder.limit,
            'messages_this_session': recorder.messages,
            'commands_this_session': dict(recorder.commands),
            'transport_diagnostics': dict(recorder.diagnostics)}
