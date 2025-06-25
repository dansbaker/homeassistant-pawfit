"""Tests for button platform."""
from __future__ import annotations

from typing import Any, Dict
from unittest.mock import AsyncMock, MagicMock, patch
import time

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from custom_components.pawfit.button import (
    PawfitFindModeButton,
    PawfitLightModeButton,
    PawfitAlarmModeButton,
    async_setup_entry,
)


class TestPawfitFindModeButton:
    """Test the PawfitFindModeButton class."""

    @pytest.fixture
    def mock_tracker(self) -> Dict[str, Any]:
        """Create a mock tracker."""
        return {
            "tracker_id": "123456",
            "name": "Buddy",
            "petId": "pet_456",
            "model": "PawFit Pro",
        }

    @pytest.fixture
    def mock_coordinator(self) -> AsyncMock:
        """Create a mock coordinator."""
        coordinator = AsyncMock()
        coordinator.data = {
            "123456": {
                "find_timer": int(time.time() * 1000),  # Current time in milliseconds
            }
        }
        coordinator.last_update_success = True
        return coordinator

    @pytest.fixture
    def find_mode_button(self, mock_tracker: Dict[str, Any], mock_coordinator: AsyncMock) -> PawfitFindModeButton:
        """Create a PawfitFindModeButton instance."""
        return PawfitFindModeButton(tracker=mock_tracker, coordinator=mock_coordinator)

    def test_find_mode_button_init(self, find_mode_button: PawfitFindModeButton) -> None:
        """Test find mode button initialization."""
        assert find_mode_button._tracker["name"] == "Buddy"
        assert find_mode_button._tracker_id == "123456"
        assert find_mode_button._attr_name == "Buddy's PawFit Tracker Find Mode"
        assert find_mode_button._attr_unique_id == "pet_456_find_mode_button"
        assert find_mode_button._attr_icon == "mdi:crosshairs-gps"

    def test_device_info(self, find_mode_button: PawfitFindModeButton) -> None:
        """Test device info property."""
        device_info = find_mode_button._attr_device_info
        assert device_info["identifiers"] == {("pawfit", "123456")}
        assert device_info["name"] == "Buddy's PawFit Tracker"
        assert device_info["model"] == "PawFit Pro"
        assert device_info["manufacturer"] == "PawFit"

    def test_available(self, find_mode_button: PawfitFindModeButton, mock_coordinator: AsyncMock) -> None:
        """Test available property."""
        assert find_mode_button.available is True

        mock_coordinator.last_update_success = False
        assert find_mode_button.available is False
    
    @pytest.mark.asyncio
    async def test_async_press_start_find_mode(self, find_mode_button: PawfitFindModeButton, mock_coordinator: AsyncMock) -> None:
        """Test pressing button to start find mode."""
        # Mock API client on coordinator.client (not api_client)
        mock_api_client = AsyncMock()
        mock_api_client.async_start_find_mode.return_value = True
        mock_coordinator.client = mock_api_client
        
        # Set find_timer to 0 (inactive)
        mock_coordinator.data = {"123456": {"find_timer": 0}}
        
        await find_mode_button.async_press()
        
        mock_api_client.async_start_find_mode.assert_called_once_with("123456")
        mock_coordinator.async_request_refresh.assert_called_once()

    @pytest.mark.asyncio
    async def test_async_press_stop_find_mode(self, find_mode_button: PawfitFindModeButton, mock_coordinator: AsyncMock) -> None:
        """Test pressing button to stop find mode."""
        # Mock API client on coordinator.client
        mock_api_client = AsyncMock()
        mock_api_client.async_stop_find_mode.return_value = True
        mock_coordinator.client = mock_api_client
        
        # Set find_timer to recent time (active)
        current_time_ms = int(time.time() * 1000)
        mock_coordinator.data = {"123456": {"find_timer": current_time_ms}}
        
        await find_mode_button.async_press()
        
        mock_api_client.async_stop_find_mode.assert_called_once_with("123456")
        mock_coordinator.async_request_refresh.assert_called_once()

    @pytest.mark.asyncio
    async def test_async_press_api_error(self, find_mode_button: PawfitFindModeButton, mock_coordinator: AsyncMock) -> None:
        """Test pressing button with API error."""
        # Mock API client to raise exception
        mock_api_client = AsyncMock()
        mock_api_client.async_start_find_mode.side_effect = Exception("API Error")
        mock_coordinator.client = mock_api_client
        
        mock_coordinator.data = {"123456": {"find_timer": 0}}
        
        with pytest.raises(HomeAssistantError, match="Error controlling find mode: API Error"):
            await find_mode_button.async_press()

    @pytest.mark.asyncio
    async def test_async_press_no_data(self, find_mode_button: PawfitFindModeButton, mock_coordinator: AsyncMock) -> None:
        """Test pressing button with no coordinator data."""
        mock_api_client = AsyncMock()
        mock_api_client.async_start_find_mode.return_value = True
        mock_coordinator.client = mock_api_client
        mock_coordinator.data = None
        
        await find_mode_button.async_press()
        
        mock_api_client.async_start_find_mode.assert_called_once_with("123456")

    def test_async_added_to_hass(self, find_mode_button: PawfitFindModeButton, mock_coordinator: AsyncMock) -> None:
        """Test async_added_to_hass method."""
        async def test():
            await find_mode_button.async_added_to_hass()
            mock_coordinator.async_add_listener.assert_called_once()

        import asyncio
        asyncio.run(test())


class TestPawfitLightModeButton:
    """Test the PawfitLightModeButton class."""

    @pytest.fixture
    def mock_tracker(self) -> Dict[str, Any]:
        """Create a mock tracker."""
        return {
            "tracker_id": "123456",
            "name": "Buddy",
            "petId": "pet_456",
        }

    @pytest.fixture
    def mock_coordinator(self) -> AsyncMock:
        """Create a mock coordinator."""
        coordinator = AsyncMock()
        coordinator.data = {
            "123456": {
                "light_timer": 0,  # Inactive
            }
        }
        coordinator.last_update_success = True
        return coordinator

    @pytest.fixture
    def light_mode_button(self, mock_tracker: Dict[str, Any], mock_coordinator: AsyncMock) -> PawfitLightModeButton:
        """Create a PawfitLightModeButton instance."""
        return PawfitLightModeButton(tracker=mock_tracker, coordinator=mock_coordinator)

    def test_light_mode_button_init(self, light_mode_button: PawfitLightModeButton) -> None:
        """Test light mode button initialization."""
        assert light_mode_button._tracker["name"] == "Buddy"
        assert light_mode_button._tracker_id == "123456"
        assert light_mode_button._attr_name == "Buddy's PawFit Tracker Light Mode"
        assert light_mode_button._attr_unique_id == "pet_456_light_mode_button"
        assert light_mode_button._attr_icon == "mdi:flashlight"
    
    @pytest.mark.asyncio
    async def test_async_press_start_light_mode(self, light_mode_button: PawfitLightModeButton, mock_coordinator: AsyncMock) -> None:
        """Test pressing button to start light mode."""
        mock_api_client = AsyncMock()
        mock_api_client.async_start_light_mode.return_value = True
        mock_coordinator.client = mock_api_client
        
        await light_mode_button.async_press()
        
        mock_api_client.async_start_light_mode.assert_called_once_with("123456")
        mock_coordinator.async_request_refresh.assert_called_once()

    @pytest.mark.asyncio
    async def test_async_press_stop_light_mode(self, light_mode_button: PawfitLightModeButton, mock_coordinator: AsyncMock) -> None:
        """Test pressing button to stop light mode."""
        mock_api_client = AsyncMock()
        mock_api_client.async_stop_light_mode.return_value = True
        mock_coordinator.client = mock_api_client
        
        # Set light_timer to recent time (active)
        current_time_ms = int(time.time() * 1000)
        mock_coordinator.data = {"123456": {"light_timer": current_time_ms}}
        
        await light_mode_button.async_press()
        
        mock_api_client.async_stop_light_mode.assert_called_once_with("123456")
        mock_coordinator.async_request_refresh.assert_called_once()


class TestPawfitAlarmModeButton:
    """Test the PawfitAlarmModeButton class."""

    @pytest.fixture
    def mock_tracker(self) -> Dict[str, Any]:
        """Create a mock tracker."""
        return {
            "tracker_id": "123456",
            "name": "Buddy",
            "petId": "pet_456",
        }

    @pytest.fixture
    def mock_coordinator(self) -> AsyncMock:
        """Create a mock coordinator."""
        coordinator = AsyncMock()
        coordinator.data = {
            "123456": {
                "alarm_timer": 0,  # Inactive
            }
        }
        coordinator.last_update_success = True
        return coordinator

    @pytest.fixture
    def alarm_mode_button(self, mock_tracker: Dict[str, Any], mock_coordinator: AsyncMock) -> PawfitAlarmModeButton:
        """Create a PawfitAlarmModeButton instance."""
        return PawfitAlarmModeButton(tracker=mock_tracker, coordinator=mock_coordinator)

    def test_alarm_mode_button_init(self, alarm_mode_button: PawfitAlarmModeButton) -> None:
        """Test alarm mode button initialization."""
        assert alarm_mode_button._tracker["name"] == "Buddy"
        assert alarm_mode_button._tracker_id == "123456"
        assert alarm_mode_button._attr_name == "Buddy's PawFit Tracker Alarm Mode"
        assert alarm_mode_button._attr_unique_id == "pet_456_alarm_mode_button"
        assert alarm_mode_button._attr_icon == "mdi:alarm-light"
    
    @pytest.mark.asyncio
    async def test_async_press_start_alarm_mode(self, alarm_mode_button: PawfitAlarmModeButton, mock_coordinator: AsyncMock) -> None:
        """Test pressing button to start alarm mode."""
        mock_api_client = AsyncMock()
        mock_api_client.async_start_alarm_mode.return_value = True
        mock_coordinator.client = mock_api_client
        
        await alarm_mode_button.async_press()
        
        mock_api_client.async_start_alarm_mode.assert_called_once_with("123456")
        mock_coordinator.async_request_refresh.assert_called_once()

    @pytest.mark.asyncio
    async def test_async_press_stop_alarm_mode(self, alarm_mode_button: PawfitAlarmModeButton, mock_coordinator: AsyncMock) -> None:
        """Test pressing button to stop alarm mode."""
        mock_api_client = AsyncMock()
        mock_api_client.async_stop_alarm_mode.return_value = True
        mock_coordinator.client = mock_api_client
        
        # Set alarm_timer to recent time (active)
        current_time_ms = int(time.time() * 1000)
        mock_coordinator.data = {"123456": {"alarm_timer": current_time_ms}}
        
        await alarm_mode_button.async_press()
        
        mock_api_client.async_stop_alarm_mode.assert_called_once_with("123456")
        mock_coordinator.async_request_refresh.assert_called_once()


class TestButtonSetup:
    """Test button platform setup."""

    @pytest.fixture
    def mock_hass(self) -> HomeAssistant:
        """Create a mock Home Assistant instance."""
        return MagicMock(spec=HomeAssistant)

    @pytest.fixture
    def mock_config_entry(self) -> MagicMock:
        """Create a mock config entry."""
        entry = MagicMock()
        entry.entry_id = "test_entry_id"
        return entry

    @pytest.fixture
    def mock_coordinator(self) -> AsyncMock:
        """Create a mock coordinator with trackers."""
        coordinator = AsyncMock()
        coordinator.trackers = [
            {
                "tracker_id": "123456",
                "name": "Buddy",
                "petId": "pet_456",
            }
        ]
        return coordinator

    def test_async_setup_entry(self, mock_hass: HomeAssistant, mock_config_entry: MagicMock, mock_coordinator: AsyncMock) -> None:
        """Test async_setup_entry function."""
        # Mock hass.data
        mock_hass.data = {
            "pawfit": {
                "test_entry_id": mock_coordinator
            }
        }

        # Mock async_add_entities
        mock_add_entities = MagicMock()

        async def test():
            await async_setup_entry(mock_hass, mock_config_entry, mock_add_entities)
            
            # Verify entities were added
            mock_add_entities.assert_called_once()
            entities = mock_add_entities.call_args[0][0]
            
            # Should create 3 buttons per tracker
            assert len(entities) == 3
            
            # Check entity types
            entity_types = [type(entity).__name__ for entity in entities]
            assert "PawfitFindModeButton" in entity_types
            assert "PawfitLightModeButton" in entity_types
            assert "PawfitAlarmModeButton" in entity_types

        import asyncio
        asyncio.run(test())
