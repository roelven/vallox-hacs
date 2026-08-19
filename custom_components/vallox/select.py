"""Support for Vallox ventilation unit select entities."""

from __future__ import annotations

from dataclasses import dataclass
from typing import override

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.const import CONF_NAME, EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import ADJUST_MODE_STR_TO_VALUE, ADJUST_MODE_TO_STR
from .coordinator import ValloxConfigEntry, ValloxDataUpdateCoordinator
from .entity import ValloxEntity


@dataclass(frozen=True, kw_only=True)
class ValloxSelectEntityDescription(SelectEntityDescription):
    """Describes a Vallox select entity backed by an integer-valued register.

    `options_map` translates the raw integer register value to the option
    string shown in the UI; `reverse_map` is its exact inverse, used to map a
    user-selected option string back to the integer written via `set_values`.
    The pattern is generic so any future enum register can be added as one
    entry in `SELECT_ENTITIES`.
    """

    metric_key: str
    options_map: dict[int, str]
    reverse_map: dict[str, int]


class ValloxSelectEntity(ValloxEntity, SelectEntity):
    """Representation of a Vallox select entity."""

    entity_description: ValloxSelectEntityDescription
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(
        self,
        name: str,
        coordinator: ValloxDataUpdateCoordinator,
        description: ValloxSelectEntityDescription,
    ) -> None:
        """Initialize the Vallox select entity."""
        super().__init__(name, coordinator)

        self.entity_description = description

        self._attr_unique_id = f"{self._device_uuid}-{description.key}"
        self._attr_options = list(description.options_map.values())

    @property
    @override
    def current_option(self) -> str | None:
        """Return the current option as a string, or None if unknown."""
        value = self.coordinator.data.get(self.entity_description.metric_key)
        if value is None:
            return None
        return self.entity_description.options_map.get(int(value))

    @override
    async def async_select_option(self, option: str) -> None:
        """Update the selected option."""
        await self.coordinator.client.set_values(
            {self.entity_description.metric_key: self.entity_description.reverse_map[option]}
        )
        await self.coordinator.async_request_refresh()


SELECT_ENTITIES: tuple[ValloxSelectEntityDescription, ...] = (
    ValloxSelectEntityDescription(
        key="supply_heating_adjust_mode",
        translation_key="supply_heating_adjust_mode",
        metric_key="A_CYC_SUPPLY_HEATING_ADJUST_MODE",
        options_map=ADJUST_MODE_TO_STR,
        reverse_map=ADJUST_MODE_STR_TO_VALUE,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ValloxConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the select entities."""
    coordinator = entry.runtime_data

    async_add_entities(
        ValloxSelectEntity(entry.data[CONF_NAME], coordinator, description)
        for description in SELECT_ENTITIES
    )
