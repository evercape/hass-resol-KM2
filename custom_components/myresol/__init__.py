"""The Resol integration."""
from __future__ import annotations

from homeassistant.config_entries import ConfigEntry

from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC

from homeassistant.core import HomeAssistant

from homeassistant.helpers import device_registry as dr

from .const import DOMAIN, PLATFORMS

from .resolapi import ResolAPI

from .const import (
    _LOGGER,
    STARTUP_MESSAGE
)

from homeassistant.helpers.translation import async_get_translations
from homeassistant.helpers import entity_registry

_LOGGER.info(STARTUP_MESSAGE)

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Resol from a config entry."""
    hass.data.setdefault(DOMAIN, {})



    #this stores an instance of the ResolAPI instance in hass.data[domain]
    #so that the sensor setup (sensor.py) can access hass.data[DOMAIN][config_entry.entry_id]
    # to retrieve the ResolAPI instance
    user_input = entry.data['user_input'] #this user_input object was stored after the device was setup and has the user/pass/host info
    device_info = entry.data.get('device_info') #this device_info object was stored after the device was setup and has the name and serial needed etc.
    options = entry.data['options'] #these are the options during setup, including custom device name
    resol_api = ResolAPI(user_input["host"], user_input["port"], user_input["username"], user_input["password"])

    if device_info:
        resol_api.device = device_info
        resol_api.options = options #store the options
    hass.data[DOMAIN][entry.entry_id] = resol_api


    # Set up the platforms like sensor, light, etc.
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Get the device registry
    device_registry = dr.async_get(hass)

    # Fetching device info from device registry
    # During the config flow, the device info is saved in the entry's data under 'device_info' key.
    device_info = entry.data.get('device_info')

    # If the device_info was provided, register the device
    if device_info:
        device_registry.async_get_or_create(
            config_entry_id=entry.entry_id,
            identifiers={(DOMAIN, device_info['serial'])},  # Using the device's MAC address
            connections = {(CONNECTION_NETWORK_MAC, device_info['mac'])},
            manufacturer=device_info.get('vendor', 'RESOL'),
            serial_number=device_info.get('serial'),
            name=options.get('custom_device_name'), #here we are taking the custom device name from user step 2
            model=device_info.get('product'),
            sw_version=device_info.get('version')
            # Additional attributes can be added if necessary
        )


    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    # Unload all platforms associated with this entry
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        # Clean up hass.data if any reference exists
        hass.data[DOMAIN].pop(entry.entry_id, None)

    return unload_ok

