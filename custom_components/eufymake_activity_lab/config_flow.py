"""Guided local Studio-file import and printer selection."""
import asyncio
import probatio as vol
from homeassistant import config_entries
from homeassistant.components.file_upload import process_uploaded_file
from homeassistant.helpers import selector
from .cloud import CloudAuthError, CloudClient, CloudError
from .const import DOMAIN
from .credentials import parse_imports


def _read_uploads(hass, uploaded):
    result = []
    for key in ("device_file", "login_file", "ca_file"):
        with process_uploaded_file(hass, uploaded[key]) as path:
            if path.stat().st_size > 2 * 1024 * 1024:
                raise ValueError("File too large")
            result.append(path.read_bytes())
    return parse_imports(*result)


def _validate_cloud(credentials):
    client = CloudClient(credentials, lambda *args: None)
    try:
        client.start()
    finally:
        client.stop()


class ActivityLabConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    def __init__(self):
        self._printers = []

    async def async_step_user(self, user_input=None):
        if self.hass.config_entries.async_entries('eufymake_e1'):
            return self.async_show_menu(step_id='user', menu_options=['existing', 'files'])
        return await self.async_step_files(user_input)

    async def async_step_existing(self, user_input=None):
        entries = self.hass.config_entries.async_entries('eufymake_e1')
        errors = {}
        if user_input is not None:
            selected = next((e for e in entries if e.entry_id == user_input.get('monitor')), None)
            if selected:
                try:
                    self._printers = [{key: selected.data[key] for key in
                        ('user_id', 'email', 'region', 'serial', 'secret_key', 'ca_pem')}]
                    return await self.async_step_printer({'printer': '0'})
                except KeyError:
                    errors['base'] = 'invalid_files'
            else:
                errors['base'] = 'invalid_selection'
        return self.async_show_form(step_id='existing', errors=errors, data_schema=vol.Schema({
            vol.Required('monitor'): selector.SelectSelector({'options':[
                {'value': e.entry_id, 'label': e.title} for e in entries], 'mode':'dropdown'})
        }))

    async def async_step_files(self, user_input=None):
        errors = {}
        if user_input is not None:
            try:
                self._printers = await self.hass.async_add_executor_job(_read_uploads, self.hass, user_input)
                if len(self._printers) == 1:
                    return await self.async_step_printer({"printer": "0"})
                return await self.async_step_printer()
            except (ValueError, OSError):
                errors["base"] = "invalid_files"
        return self.async_show_form(step_id="files", errors=errors, data_schema=vol.Schema({
            vol.Required("device_file"): selector.FileSelector({"accept": ".json"}),
            vol.Required("login_file"): selector.FileSelector({"accept": ".json"}),
            vol.Required("ca_file"): selector.FileSelector({"accept": ".crt,.pem"}),
        }))

    async def async_step_printer(self, user_input=None):
        if not self._printers:
            return await self.async_step_user()
        errors = {}
        if user_input is not None:
            try:
                index = int(user_input["printer"])
                if not 0 <= index < len(self._printers):
                    raise ValueError("Invalid selection")
                credentials = self._printers[index]
                serial = credentials["serial"]
                await self.async_set_unique_id(serial)
                reauth = self.context.get("source") == config_entries.SOURCE_REAUTH
                if reauth:
                    entry = self._get_reauth_entry()
                    if entry.unique_id != serial:
                        errors["base"] = "wrong_printer"
                else:
                    self._abort_if_unique_id_configured()
                if not errors:
                    await self.hass.async_add_executor_job(_validate_cloud, credentials)
                    self._printers = []
                    if reauth:
                        return self.async_update_reload_and_abort(entry, data_updates=credentials)
                    return self.async_create_entry(title="Activity Lab · " + serial[-6:], data=credentials)
            except CloudAuthError:
                errors["base"] = "invalid_auth"
            except (CloudError, OSError, asyncio.TimeoutError):
                errors["base"] = "cannot_connect"
            except (ValueError, KeyError, IndexError):
                errors["base"] = "invalid_selection"
        return self.async_show_form(step_id="printer", errors=errors, data_schema=vol.Schema({
            vol.Required("printer", default="0"): selector.SelectSelector({
                "options": [{"value": str(i), "label": "Activity Lab · " + device["serial"][-6:]} for i, device in enumerate(self._printers)],
                "mode": "dropdown",
            }),
        }))

    async def async_step_reauth(self, entry_data):
        return await self.async_step_user()
