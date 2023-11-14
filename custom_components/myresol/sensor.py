from homeassistant.components.sensor import SensorEntity
from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.components.sensor import SensorStateClass

from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers import entity_registry
from homeassistant.helpers.entity_registry import async_get
from homeassistant.helpers.entity_registry import async_get as async_get_entity_registry


from homeassistant.config_entries import ConfigEntry

from homeassistant import config_entries
from homeassistant import exceptions

from homeassistant.exceptions import HomeAssistantError
from homeassistant.exceptions import IntegrationError

from datetime import timedelta
from datetime import datetime

import asyncio
from collections import defaultdict

from .const import (
    DOMAIN,
    _LOGGER,
    ATTR_PRODUCT_DESCRIPTION,
    ATTR_DESTINATION_NAME,
    ATTR_SOURCE_NAME,
    ATTR_UNIQUE_ID,
    ATTR_PRODUCT_SERIAL,
    ATTR_PRODUCT_NAME,
    ATTR_PRODUCT_VENDOR,
    ATTR_PRODUCT_BUILD,
    ATTR_PRODUCT_VERSION,
    ATTR_PRODUCT_FEATURES,
    ISSUE_URL_ERROR_MESAGE
)


from .resolapi import ResolAPI


device_specific_sensors = {}


# Setting up the adding and updating of sensor entities
async def async_setup_entry(hass, config_entry, async_add_entities):

    # Retrieve the API instance from the config_entry data
    resol_api = hass.data[DOMAIN][config_entry.entry_id]

    # Fetch the sensor data from the KM2 device
    try:
        data = await hass.async_add_executor_job(resol_api.fetch_data_km2)

    except IntegrationError as error:
        _LOGGER.error(f"{resol_api.device['serial']}: Failed to fetch sensor data: {error}"+ISSUE_URL_ERROR_MESAGE)
        return


    # Get device id and then reset the device specific list of sensors for updates to ensure it's empty before adding new entries
    device_id = resol_api.device['serial']  # Or any other unique identifier for the device
    _LOGGER.debug(f"{resol_api.device['serial']}: Device ID: {device_id}")
    device_specific_sensors[device_id] = []


    #Registering entities to registry, and adding them to list for schedule updates on each device
    for unique_id, endpoint in data.items():
        sensor = ResolSensor(resol_api, endpoint)
        device_specific_sensors[device_id].append(sensor)
        async_add_entities([sensor], False)

    _LOGGER.debug(f"{resol_api.device['serial']}: List of device_specific_sensors[device_id]: {device_specific_sensors[device_id]}")

    _LOGGER.info(f"{resol_api.device['serial']}: All '{len(device_specific_sensors[device_id])}' sensors have registered.")




    # Schedule updates
    async def async_update_data(now):
        _LOGGER.debug(f"{resol_api.device['serial']}: Preparing to update sensor data via async_update_data() at {now}")

        # Fetch the full dataset once from the API
        try:
            full_data = await hass.async_add_executor_job(resol_api.fetch_data_km2)
        except Exception as e:
            _LOGGER.error(f"{resol_api.device['serial']}: Error fetching data from the device: {e}"+ISSUE_URL_ERROR_MESAGE)
            return


        """
        # Fetch the registry and check if sensors are enabled
        registry = entity_registry.async_get(hass)

        # Set counters to zero
        counter_updated = 0     # Successfully updated sensors
        counter_disabled = 0    # Disabled sensors, not to be updated
        counter_unchanged = 0   # Skipped sensors since value has not changed
        counter_error = 0       # Skipped sensors due to some error, such as registry not found or no data from API
        update_sensor = False   # Flag to decide if sensor is udpated or not

        # Loop through the full set of API data received
        #for unique_id, endpoint in full_data.items():
        for sensor in device_specific_sensors[device_id]:
            #_LOGGER.error(endpoint.name)
            #_LOGGER.error(endpoint.value)

            # Get the corresponding entity_id and entity from registry with disabled_by attributes
            entity_id = registry.async_get_entity_id('sensor', DOMAIN, unique_id)
            if entity_id:
                entity = registry.entities.get(entity_id)
                _LOGGER.debug(f"{resol_api.device['serial']}: Sensor '{endpoint.name}' corresponding entity_id found {entity_id}")
                if entity and not entity.disabled_by:
                    sensor_data = full_data.get(unique_id)
                    _LOGGER.debug(f"{resol_api.device['serial']}: Sensor '{endpoint.name}' is not disabled.")
                    if sensor_data:
                        _LOGGER.debug(f"{resol_api.device['serial']}: Sensor '{endpoint.name}' has API data eligible for update {sensor_data}")
                        # Check if current sensor state  exist
                        state = hass.states.get(entity_id)
                        if state is not None:
                            _LOGGER.debug(f"{resol_api.device['serial']}: Sensor '{endpoint.name}' initiliazed and has state data {state}.")
                            # Check if current state value is the same as new API value
                            if str(state.state).strip() == str(endpoint.value).strip():
                                # Don't update sensor since it has the same value
                                _LOGGER.debug(f"{resol_api.device['serial']}: Sensor '{endpoint.name}' skipped as current value '{state.state}' same as new value '{endpoint.value}'")
                                counter_unchanged = counter_unchanged + 1
                                update_sensor = False
                            else:
                                update_sensor = True
                                _LOGGER.debug(f"{resol_api.device['serial']}: Sensor '{endpoint.name}' marked for update as current value '{state.state}' is not the same as new value '{endpoint.value}'")
                        else:
                            update_sensor = True
                            _LOGGER.warning(f"{resol_api.device['serial']}: Sensor '{endpoint.name}' marked for update as it did not initiliaze and has no state data {state}.")

                    # Update Sensor as current value either not initialized or not the same as new value
                        if update_sensor == True:
                            _LOGGER.debug(f"{resol_api.device['serial']}: Attempting to update sensor '{endpoint.name}' from current value '{state.state}' to new value '{endpoint.value}'")
                            #sensor = ResolSensor(resol_api, endpoint)
                            update_status = await sensor.async_update(sensor_data) #update_status returns 1 for upated, 0 for skipped or error
                            if update_status==1:
                                _LOGGER.debug(f"{resol_api.device['serial']}: Sensor '{endpoint.name}' updated from current value '{state.state}' to new value '{endpoint.value}'")
                            else:
                                _LOGGER.debug(f"{resol_api.device['serial']}: Sensor '{endpoint.name}' occured an eror whilst trying to updat from current value '{state.state}' to new value '{endpoint.value}'")
                            counter_updated = counter_updated + update_status

                    else:
                        _LOGGER.warning(f"{resol_api.device['serial']}: No update data found for sensor '{endpoint.name}'"+ISSUE_URL_ERROR_MESAGE)
                        counter_error = counter_error + 1
                else:
                    _LOGGER.debug(f"{resol_api.device['serial']}: Sensor '{endpoint.name}' is disabled, skipping update")
                    counter_disabled = counter_disabled + 1
            else:
                _LOGGER.warning(f"{resol_api.device['serial']}: Sensor '{endpoint.name}' not found in the registry, skipping update"+ISSUE_URL_ERROR_MESAGE)
                counter_error = counter_error + 1


        # Log summary of updates
        _LOGGER.info(f"{resol_api.device['serial']}: A total of '{counter_updated}' sensors have updated, '{counter_disabled}' are disabled and skipped update, '{counter_unchanged}' sensors value remained constant and '{counter_error}' sensors occured any errors.")
        """









        # Fetch the registry and check if sensors are enabled
        registry = entity_registry.async_get(hass)


        # Set counters to zero
        counter_updated = 0     # Successfully updated sensors
        counter_disabled = 0    # Disabled sensors, not to be updated
        counter_unchanged = 0   # Skipped sensors since value has not changed
        counter_error = 0       # Skipped sensors due to some error, such as registry not found or no data from API

        # Now loop through the sensors to be updated
        for sensor in device_specific_sensors[device_id]:
            entity_id = registry.async_get_entity_id('sensor', DOMAIN, sensor.unique_id)
            if entity_id:
                entity = registry.entities.get(entity_id)
                if entity and not entity.disabled_by:
                    sensor_data = full_data.get(sensor.unique_id)
                    _LOGGER.debug(f"{resol_api.device['serial']}: Sensor '{sensor.name}' is not disabled.")
                    if sensor_data:
                        _LOGGER.debug(f"{resol_api.device['serial']}: Sensor '{sensor.name}' has API data eligible for update {sensor_data}")

                        # Check if current state value differs from new API value, or current state has not initialized
                        if str(sensor._state).strip() != str(sensor_data.value).strip():
                            _LOGGER.debug(f"{resol_api.device['serial']}: Sensor '{sensor.name}' marked for update as current value '{sensor._state}' is not the same as new value '{sensor_data.value}'")
                            # Now update the sensor with new values
                            update_status = await sensor.async_update(sensor_data) #update_status returns 1 for upated, 0 for skipped or error
                            counter_updated = counter_updated + update_status
                        else:
                            _LOGGER.debug(f"{resol_api.device['serial']}: Sensor '{sensor.name}' skipped as current value '{sensor._state}' same as new value '{sensor_data.value}'")
                            counter_unchanged = counter_unchanged + 1
                    else:
                        _LOGGER.warning(f"{resol_api.device['serial']}: No update data found for sensor '{sensor.name}'"+ISSUE_URL_ERROR_MESAGE)
                        counter_error = counter_error + 1
                else:
                    _LOGGER.debug(f"{resol_api.device['serial']}: Sensor '{sensor.name}' is disabled, skipping update")
                    counter_disabled = counter_disabled + 1
            else:
                _LOGGER.warning(f"{resol_api.device['serial']}: Sensor '{sensor.name}' not found in the registry, skipping update"+ISSUE_URL_ERROR_MESAGE)
                counter_error = counter_error + 1


        # Log summary of updates
        _LOGGER.info(f"{resol_api.device['serial']}: A total of '{counter_updated}' sensors have updated, '{counter_disabled}' are disabled and skipped update, '{counter_unchanged}' sensors value remained constant and '{counter_error}' sensors occured any errors.")



    # Get the polling interval from the options, defaulting to 60 seconds if not set
    polling_interval = timedelta(seconds=config_entry.options.get('polling_interval', 60))
    async_track_time_interval(hass, async_update_data, polling_interval)






#This is the actual instance of SensorEntity class
class ResolSensor(SensorEntity):
    """Representation of a RESOL Temperature Sensor."""

    def __init__(self, resol_api: ResolAPI, endpoint):

        """Initialize the sensor."""
        # Make the ResolAPI and the endpoint parameters from the Sensor API available
        self.resol_api = resol_api
        self.endpoint = endpoint

        # Set Friendly name whilst created first
        self._attr_unique_id = endpoint.name #<-- MARTIN5000 this is questionable maybe this causes the issue????
        self._attr_has_entity_name = True
        self._attr_name = endpoint.friendly_name
        self._name = endpoint.friendly_name

        # The unique identifier for this sensor within Home Assistant
        # Has nothing to do with the entity_id, it is the internal unique_id of the sensor entity registry
        self._unique_id = endpoint.internal_unique_id

        # Set the icon for the sensor based on its unit, ensure the icon_mapper is defined
        self._icon = ResolSensor.icon_mapper.get(endpoint.unit)  # Default handled in function

        # The initial state/value of the sensor
        self._state = endpoint.value

        # The unit of measurement for the sensor
        self._unit = endpoint.unit
        #_LOGGER.debug(f"Assigned icon: {self._icon} for unit: {self._unit} of sensor {self._name}")

        # Set entity category to diagnostic for sensors with no unit
        if resol_api.options.get("group_sensors") and not endpoint.unit:
            self._attr_entity_category = EntityCategory.DIAGNOSTIC

        # Decide whether the diagnostics entity should be enabled or disabled by default
        if resol_api.options.get("disable_sensors") and not endpoint.unit:
            self._attr_entity_registry_enabled_default = False


    @property
    def should_poll(self):
        """ No need to poll. async_track_time_intervals handles entity of updates. """
        return False

    @property
    def unique_id(self):
        """Return the unique ID of the sensor."""
        return self._unique_id

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name


    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        return self._unit

    @property
    def device_class(self):
        """ Return the device class of this entity, if any. """
        if self._unit == '°C':
            return SensorDeviceClass.TEMPERATURE
        elif self._unit == '%':
            return SensorDeviceClass.POWER_FACTOR
        elif self._unit == 'Wh':
            return SensorDeviceClass.ENERGY
        else:
            return None

    @property
    def state_class(self):
        """ Return the state class of this entity, if any. """
        if self._unit == '°C':
            return SensorStateClass.MEASUREMENT
        elif self._unit == 'h':
            return SensorStateClass.MEASUREMENT
        elif self._unit == 'Wh':
            return SensorStateClass.TOTAL_INCREASING
        else:
            return None

    @property
    def extra_state_attributes(self):
        """ Return the state attributes of this device. """
        attr = {}

        attr[ATTR_PRODUCT_DESCRIPTION] = self.endpoint.description
        attr[ATTR_DESTINATION_NAME] = self.endpoint.destination
        attr[ATTR_SOURCE_NAME] = self.endpoint.source
        attr[ATTR_UNIQUE_ID] = self.endpoint.internal_unique_id
        attr[ATTR_PRODUCT_VENDOR] = self.resol_api.device['vendor']
        attr[ATTR_PRODUCT_NAME] = self.resol_api.device['name']
        attr[ATTR_PRODUCT_SERIAL] = self.endpoint.serial
        attr[ATTR_PRODUCT_VERSION] = self.resol_api.device['version']
        attr[ATTR_PRODUCT_BUILD] = self.resol_api.device['build']
        attr[ATTR_PRODUCT_FEATURES] = self.resol_api.device['features']

        return attr

    @property
    def device_info(self):
        """Return device specific attributes."""
        # Use whatever identifiers are unique to the device
        return {
            'identifiers': {(DOMAIN, self.resol_api.device['serial'])},
            'name': self.resol_api.device['name'],
            'manufacturer': 'RESOL',

        }

    icon_mapper = defaultdict(lambda: "mdi:alert-circle", {
        '°C': 'mdi:thermometer',
        '%': 'mdi:flash',
        'l/h': 'mdi:hydro-power',
        'bar': 'mdi:car-brake-low-pressure',
        '%RH': 'mdi:water-percent',
        's': 'mdi:timer',
        'Wh': 'mdi:solar-power-variant-outline',
        'h': 'mdi:timer-sand'
        })


    # This is to register the icon settings
    async def async_added_to_hass(self):
        """Call when the sensor is added to Home Assistant."""
        # Now it's safe to call this because the entity has been added to HA
        self.async_write_ha_state()


    #update of Sensor values
    async def async_update(self, sensor_data=None):
        """Update the sensor with the provided data."""
        if sensor_data is None:
            _LOGGER.warning(f"{self.resol_api.device['serial']}: No new data provided for sensor '{self.name}' update"+ISSUE_URL_ERROR_MESAGE)
            update_status = 0
            return

        try:
            self._state = sensor_data.value
            update_status = 1
            self.async_write_ha_state()

        except Exception as error:
            _LOGGER.error(f"{self.resol_api.device['serial']}: Error updating sensor {self.name}: {error}"+ISSUE_URL_ERROR_MESAGE)
            update_status = 0

        return update_status



