"""Tests for Pawfit device tracker entity."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from homeassistant.components.device_tracker import SourceType
from homeassistant.const import STATE_HOME, STATE_NOT_HOME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import UpdateFailed
from homeassistant.helpers.entity import DeviceInfo

from custom_components.pawfit.const import DOMAIN
from custom_components.pawfit.device_tracker import PawfitDeviceTracker, PawfitDataUpdateCoordinator


class TestPawfitDeviceTracker:
    """Test the PawfitDeviceTracker class."""

    @pytest_asyncio.fixture
    async def mock_coordinator(self) -> AsyncMock:
        """Create a mock coordinator."""
        coordinator = AsyncMock()
        coordinator.data = {
            "tracker_123": {
                "latitude": 37.7749,
                "longitude": -122.4194,
                "utcDateTime": 1640995200000,  # 2022-01-01 00:00:00 UTC
                "accuracy": 10.5,
                "battery": 85,
                "last_seen": 1640995200000
            }
        }
        coordinator.last_update_success = True
        coordinator.config_entry = MagicMock()
        coordinator.config_entry.entry_id = "test_entry_id"
        return coordinator

    @pytest_asyncio.fixture
    async def tracker_dict(self) -> Dict[str, Any]:
        """Create a tracker dictionary for testing."""
        return {
            "name": "Buddy",
            "petId": "pet_456",
            "tracker_id": "tracker_123",
            "model": "PawFit Gen 2"
        }

    @pytest_asyncio.fixture
    async def device_tracker(self, tracker_dict: Dict[str, Any], mock_coordinator: AsyncMock) -> PawfitDeviceTracker:
        """Create a device tracker entity for testing."""
        return PawfitDeviceTracker(tracker_dict, mock_coordinator)

    def test_device_tracker_init(self, device_tracker: PawfitDeviceTracker, mock_coordinator: AsyncMock) -> None:
        """Test device tracker initialization."""
        assert device_tracker._coordinator == mock_coordinator
        assert device_tracker._tracker_id == "tracker_123"
        assert device_tracker._tracker["name"] == "Buddy"
        assert device_tracker._tracker["petId"] == "pet_456"

    def test_device_info(self, device_tracker: PawfitDeviceTracker) -> None:
        """Test device info property."""
        device_info = device_tracker.device_info
        
        assert isinstance(device_info, dict)
        assert device_info["identifiers"] == {(DOMAIN, "tracker_123")}
        assert device_info["name"] == "Buddy's PawFit Tracker"
        assert device_info["manufacturer"] == "PawFit"
        assert device_info["model"] == "PawFit Gen 2"

    def test_unique_id(self, device_tracker: PawfitDeviceTracker) -> None:
        """Test unique ID property."""
        assert device_tracker.unique_id == "pet_456"

    def test_name(self, device_tracker: PawfitDeviceTracker) -> None:
        """Test name property."""
        assert device_tracker.name == "Buddy's PawFit Tracker"

    def test_source_type(self, device_tracker: PawfitDeviceTracker) -> None:
        """Test source type property."""
        assert device_tracker.source_type == SourceType.GPS

    def test_latitude(self, device_tracker: PawfitDeviceTracker) -> None:
        """Test latitude property."""
        device_tracker._update_attrs()  # Trigger update to populate attributes
        assert device_tracker.latitude == 37.7749

    def test_longitude(self, device_tracker: PawfitDeviceTracker) -> None:
        """Test longitude property."""
        device_tracker._update_attrs()  # Trigger update to populate attributes
        assert device_tracker.longitude == -122.4194

    def test_location_accuracy(self, device_tracker: PawfitDeviceTracker) -> None:
        """Test location accuracy property."""
        device_tracker._update_attrs()  # Trigger update to populate attributes
        assert device_tracker.location_accuracy == 10.5

    def test_battery_level(self, device_tracker: PawfitDeviceTracker) -> None:
        """Test battery level property."""
        device_tracker._update_attrs()  # Trigger update to populate attributes
        assert device_tracker.battery_level == 85

    def test_battery_level_negative_charging(self, device_tracker: PawfitDeviceTracker, mock_coordinator: AsyncMock) -> None:
        """Test battery level with negative value (charging)."""
        # Set battery to negative value to simulate charging
        mock_coordinator.data["tracker_123"]["battery"] = -75
        device_tracker._update_attrs()
        # Should return positive value
        assert device_tracker.battery_level == 75

    def test_available(self, device_tracker: PawfitDeviceTracker, mock_coordinator: AsyncMock) -> None:
        """Test available property."""
        # Set up conditions for availability
        mock_coordinator.last_update_success = True
        device_tracker._attr_latitude = 40.7128
        device_tracker._attr_longitude = -74.0060
        assert device_tracker.available == True
        
        # Test with no location data
        device_tracker._attr_latitude = None
        device_tracker._attr_longitude = None
        assert device_tracker.available == False
        
        # Test with coordinator failure
        device_tracker._attr_latitude = 40.7128
        device_tracker._attr_longitude = -74.0060
        mock_coordinator.last_update_success = False
        assert device_tracker.available == False

    def test_no_location_data(self, device_tracker: PawfitDeviceTracker, mock_coordinator: AsyncMock) -> None:
        """Test device tracker with no location data."""
        # Remove location data
        mock_coordinator.data = {}
        device_tracker._update_attrs()
        
        assert device_tracker.latitude is None
        assert device_tracker.longitude is None
        assert device_tracker.location_accuracy is None
        assert device_tracker.battery_level is None

    def test_partial_location_data(self, device_tracker: PawfitDeviceTracker, mock_coordinator: AsyncMock) -> None:
        """Test device tracker with partial location data."""
        # Set only latitude
        mock_coordinator.data["tracker_123"] = {"latitude": 37.7749}
        device_tracker._update_attrs()
        
        assert device_tracker.latitude == 37.7749
        assert device_tracker.longitude is None
        assert device_tracker.location_accuracy is None

    @pytest.mark.asyncio
    async def test_async_update(self, device_tracker: PawfitDeviceTracker, mock_coordinator: AsyncMock) -> None:
        """Test async update method."""
        await device_tracker.async_update()
        mock_coordinator.async_request_refresh.assert_called_once()

    @pytest.mark.asyncio
    async def test_async_added_to_hass(self, device_tracker: PawfitDeviceTracker) -> None:
        """Test async added to hass method."""
        with patch.object(device_tracker, 'async_on_remove') as mock_on_remove:
            await device_tracker.async_added_to_hass()
            mock_on_remove.assert_called_once()

    def test_handle_coordinator_update(self, device_tracker: PawfitDeviceTracker) -> None:
        """Test coordinator update handler."""
        with patch.object(device_tracker, '_update_attrs') as mock_update_attrs, \
             patch.object(device_tracker, 'async_write_ha_state') as mock_write_state:
            device_tracker._handle_coordinator_update()
            mock_update_attrs.assert_called_once()
            mock_write_state.assert_called_once()


class TestPawfitDataUpdateCoordinatorDeviceTracker:
    """Test the PawfitDataUpdateCoordinator class with device tracker context."""

    @pytest_asyncio.fixture
    async def mock_hass(self) -> MagicMock:
        """Create a mock Home Assistant instance."""
        hass = MagicMock()
        hass.data = {}
        return hass

    @pytest_asyncio.fixture
    async def mock_api_client(self) -> AsyncMock:
        """Create a mock API client."""
        api_client = AsyncMock()
        api_client.async_get_locations.return_value = {
            "tracker_123": {
                "latitude": 37.7749,
                "longitude": -122.4194,
                "accuracy": 10.5
            }
        }
        api_client.async_get_detailed_status.return_value = {
            "tracker_123": {"battery": 85}
        }
        return api_client

    @pytest_asyncio.fixture
    async def trackers_list(self) -> list:
        """Create a list of tracker dictionaries."""
        return [
            {
                "name": "Buddy",
                "petId": "pet_456",
                "tracker_id": "tracker_123",
                "model": "PawFit Gen 2"
            }
        ]

    @pytest_asyncio.fixture
    async def coordinator(self, mock_hass: MagicMock, mock_api_client: AsyncMock, trackers_list: list) -> PawfitDataUpdateCoordinator:
        """Create a coordinator for testing."""
        return PawfitDataUpdateCoordinator(mock_hass, mock_api_client, trackers_list)

    @pytest.mark.asyncio
    async def test_coordinator_init(self, coordinator: PawfitDataUpdateCoordinator, mock_api_client: AsyncMock, trackers_list: list) -> None:
        """Test coordinator initialization."""
        assert coordinator.client == mock_api_client
        assert coordinator.trackers == trackers_list
        assert coordinator.tracker_ids == ["tracker_123"]

    @pytest.mark.asyncio
    async def test_coordinator_update_data_success(self, coordinator: PawfitDataUpdateCoordinator) -> None:
        """Test successful data update."""
        data = await coordinator._async_update_data()
        
        assert "tracker_123" in data
        assert data["tracker_123"]["latitude"] == 37.7749
        assert data["tracker_123"]["longitude"] == -122.4194
        assert data["tracker_123"]["accuracy"] == 10.5

    @pytest.mark.asyncio
    async def test_coordinator_check_any_mode_active(self, coordinator: PawfitDataUpdateCoordinator) -> None:
        """Test checking if any mode is active."""
        # Test with no timers
        data = {"tracker_123": {}}
        assert coordinator._check_any_mode_active(data) == False
        
        # Test with active find timer
        data = {"tracker_123": {"find_timer": 1234567890000}}
        with patch('time.time', return_value=1234567890):
            assert coordinator._check_any_mode_active(data) == True

    def test_coordinator_update_polling_interval(self, coordinator: PawfitDataUpdateCoordinator) -> None:
        """Test updating polling interval."""
        # Start with default interval
        assert coordinator.update_interval == coordinator._default_interval
        
        # Test with active mode
        data = {"tracker_123": {"find_timer": 1234567890000}}
        with patch('time.time', return_value=1234567890):
            coordinator._update_polling_interval(data)
            assert coordinator.update_interval == coordinator._fast_interval

    @pytest.mark.asyncio
    async def test_coordinator_set_fast_polling(self, coordinator: PawfitDataUpdateCoordinator) -> None:
        """Test setting fast polling."""
        # Start with default interval
        assert coordinator.update_interval == coordinator._default_interval
        
        await coordinator.async_set_fast_polling()
        assert coordinator.update_interval == coordinator._fast_interval
