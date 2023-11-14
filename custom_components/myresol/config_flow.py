"""Config flow for Resol integration."""
from __future__ import annotations

import logging
import re
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant import exceptions

from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import HomeAssistantError
from homeassistant.exceptions import IntegrationError

from .const import (
    DOMAIN,
    ISSUE_URL_ERROR_MESAGE
)

from .resolapi import ResolAPI

_LOGGER = logging.getLogger(__name__)

# This is the first step's schema when setting up the integration, or its devices
# The second schema is defined inside the ConfigFlow class as it has dynamice default values set via API call
# 192.168.0.46 / 80 / admin / Zbm8DgKm
# http://benguelacove.dyndns.org / 8005 / admin / 9kqdtEOp
STEP_USER_DATA_SCHEMA = vol.Schema(
    {

        vol.Required("host", default="benguelacove.dyndns.org"): str,
        vol.Required("port", default="8005"): str,
        vol.Required("username", default="admin"): str,
        vol.Required("password", default="9kqdtEOp"): str,
    }
)



async def validate_input_for_device(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    """Validate the user input allows us to connect."""

    resol_api = ResolAPI(data["host"], data["port"], data["username"], data["password"])

    try:
        #calls the ResolAPI with the detect_device method
        device = await hass.async_add_executor_job(resol_api.detect_device)

        #and returns the device object with the device information
        return device
    except IntegrationError as e:
        _LOGGER.error(f"Failed to connect to Resol device: {e}"+ISSUE_URL_ERROR_MESAGE)
        raise CannotConnect from e



class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Resol."""

    VERSION = 1

    # Make sure user input data is passed from one step to the next using user_input_from_step_user
    def __init__(self):
        self.user_input_from_step_user = None

    # This is step 1 for the host/port/user/pass function.
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                #valide the user input whilst setting up integration or adding new devices.
                #validate_input_for_devices will try to detect the device and get more info fromit
                device = await validate_input_for_device(self.hass, user_input)
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                #create a unique device id as a combination of the device's product and its serial number (which should be unique on its own)
                #the host can be udpated if necessary, as the IP address of the device may have changed
                unique_id = f"{device['product']}_{device['serial']}"

                #checks that the device is actually unique, otherwise abort
                await self.async_set_unique_id(unique_id)
                self._abort_if_unique_id_configured(updates={"host": user_input["host"]})

                # Before creating the entry in the config_entry registry, go to step 2 for the options
                # However, make sure the steps from the user input are passed on to the next step
                self.user_input_from_step_user = user_input
                self.device_info = device
                # Now call the second step but set user_input to None for the first time to force data entry in step 2
                #return await self.async_step_device_options(device_info=device, user_input=None)
                return await self.async_step_device_options(user_input=None)

                #async_create_entry will trigger the entry in the config_entry via __init__.py's async_setup_entry() function.
                #device_info has the device object with all the information.
                #return self.async_create_entry(title=device["name"], data={"user_input": user_input, "device_info": device})

        # Show the form for step 1 with the user/host/pass as defined in STEP_USER_DATA_SCHEMA
        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )

    # This is step 2 for the options such as custom name, group and disable sensors
    #async def async_step_device_options(self, device_info: dict[str, Any], user_input: dict[str, Any] | None = None) -> FlowResult:
    async def async_step_device_options(
        self, user_input: dict[str, Any] | None = None,
    ) -> FlowResult:
        """Handle the device options step."""

        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                #Sanitize the user provided custom device name, which is used for entry and device registry name
                user_input["custom_device_name"] = sanitize_device_name(user_input["custom_device_name"], self.device_info["name"])

                # Since we have already set the unique ID and updated host if necessary,
                # we create the entry with the additional options.
                # The title of the integration is the custom friendly device name given by the user in step 2
                title = user_input["custom_device_name"]
                return self.async_create_entry(
                    title=title,
                    data={
                        "user_input": self.user_input_from_step_user,  # from previous step
                        "device_info": self.device_info,  # from device detection
                        "options": user_input  # new options from this step
                    },
                )
            except Exception as e:
                _LOGGER.error(f"Failed to handle device options: {e}"+ISSUE_URL_ERROR_MESAGE)
                errors["base"] = "option_error"

        # Prepare the second form's schema as it has dynamic values based on the API call
        # Use the name from the detected device as default device name
        default_device_name = self.device_info["name"] if self.device_info and "name" in self.device_info else "New Device"
        step_device_options_schema = vol.Schema({
            vol.Required("custom_device_name", default=default_device_name): str,
            vol.Required("polling_time", default=60): vol.All(vol.Coerce(int), vol.Clamp(min=60)),
            vol.Required("group_sensors", default=True): bool,
            vol.Required("disable_sensors", default=True): bool,
        })

        # Show the form for step 2 with the device name and other options as defined in STEP_DEVICE_OPTIONS_SCHEMA
        return self.async_show_form(
            step_id="device_options",
            data_schema=step_device_options_schema,
            errors={},
        )




class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""


#Helper function to sanitize
def sanitize_device_name(device_name: str, fall_back: str, max_length=255) -> str:
    # Trim whitespace
    name = device_name.strip()

    # Remove special characters but keep spaces
    name = re.sub(r'[^\w\s-]', '', name)

    # Replace multiple spaces with a single space
    name = re.sub(r'\s+', ' ', name)

    # Length check
    if len(name) > max_length:
        name = name[:max_length].rsplit(' ', 1)[0]  # Split at the last space to avoid cutting off in the middle of a word

    # Fallback name
    if not name:
        name = fall_back

    return name