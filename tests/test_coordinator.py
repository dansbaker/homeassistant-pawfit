"""Tests for Pawfit data coordinator."""
from __future__ import annotations

from datetime import timedelta
from typing import Any, Dict
from unittest.mock import AsyncMock, MagicMock

import pytest
from homeassistant.core import HomeAssistant

from custom_components.pawfit.device_tracker import PawfitDataUpdateCoordinator
from custom_components.pawfit.pawfit_api import PawfitApiClient


class TestPawfitDataUpdateCoordinator:
    """Test the PawfitDataUpdateCoordinator class."""

    @pytest.fixture
    def mock_api_client(self) -> AsyncMock:
        """Create a mock API client."""
        client = AsyncMock(spec=PawfitApiClient)
        
        # Mock location data
        client.async_get_locations.return_value = {
            "tracker_456": {
                "latitude": 40.7128,
                "longitude": -74.0060,
                "accuracy": 10.0,
                "last_update": 1640995200000,
                "battery": 85,
                "signal": -70,
                "_raw": {
                    "state": {
                        "location": {
                            "latitude": 40.7128,
                            "longitude": -74.0060,
                            "accuracy": 10.0,
                            "utcDateTime": 1640995200
                        },
                        "power": 85,
                        "signal": -70
                    }
                }
            }
        }
        
        # Mock detailed status
        client.async_get_detailed_status.return_value = {
            "tracker_456": {
                "timerGps": 0,
                "timerLight": 0,
                "timerSpeaker": 0
            }
        }
        
        # Mock activity stats
        client.async_get_activity_stats.return_value = {
            "total_steps": 1500,
            "total_calories": 120.5,
            "total_active_hours": 3.2
        }
        
        return client

    @pytest.fixture
    def mock_trackers(self) -> list[Dict[str, Any]]:
        """Create mock tracker data."""
        return [
            {
                "name": "Buddy",
                "petId": "pet_123",
                "tracker_id": "tracker_456",
                "model": "PawFit Tracker v2"
            }
        ]

    @pytest.fixture
    def coordinator(
        self, 
        hass: HomeAssistant, 
        mock_api_client: AsyncMock, 
        mock_trackers: list[Dict[str, Any]]
    ) -> PawfitDataUpdateCoordinator:
        """Create a coordinator instance."""
        return PawfitDataUpdateCoordinator(hass, mock_api_client, mock_trackers)

    def test_init(
        self, 
        coordinator: PawfitDataUpdateCoordinator, 
        mock_trackers: list[Dict[str, Any]]
    ) -> None:
        """Test coordinator initialization."""
        assert coordinator.client is not None
        assert coordinator.trackers == mock_trackers
        assert coordinator.tracker_ids == ["tracker_456"]
        assert coordinator.update_interval == timedelta(seconds=60)
        assert coordinator._default_interval == timedelta(seconds=60)
        assert coordinator._fast_interval == timedelta(seconds=1)

    @pytest.mark.asyncio
    async def test_update_data_success(
        self, 
        coordinator: PawfitDataUpdateCoordinator,
        mock_api_client: AsyncMock
    ) -> None:
        """Test successful data update."""
        data = await coordinator._async_update_data()
        
        assert "tracker_456" in data
        tracker_data = data["tracker_456"]
        assert tracker_data["latitude"] == 40.7128
        assert tracker_data["longitude"] == -74.0060
        assert tracker_data["battery"] == 85
        assert tracker_data["find_timer"] == 0
        assert tracker_data["light_timer"] == 0
        assert tracker_data["alarm_timer"] == 0
        assert tracker_data["steps_today"] == 1500
        assert tracker_data["calories_today"] == 120.5
        assert tracker_data["active_time_today"] == 3.2
        
        # Verify API calls were made
        mock_api_client.async_get_locations.assert_called_once_with(["tracker_456"])
        mock_api_client.async_get_detailed_status.assert_called_once_with(["tracker_456"])
        mock_api_client.async_get_activity_stats.assert_called_once_with("tracker_456")

    def test_check_any_mode_active_no_data(
        self, 
        coordinator: PawfitDataUpdateCoordinator
    ) -> None:
        """Test mode check with no data."""
        result = coordinator._check_any_mode_active(None)
        assert result is False
        
        result = coordinator._check_any_mode_active({})
        assert result is False

    def test_check_any_mode_active_with_timers(
        self, 
        coordinator: PawfitDataUpdateCoordinator
    ) -> None:
        """Test mode check with active timers."""
        import time
        current_time = time.time() * 1000  # Convert to milliseconds
        
        # Test with active find timer (recent timestamp)
        data = {
            "tracker_456": {
                "find_timer": current_time - 30000,  # 30 seconds ago
                "light_timer": 0,
                "alarm_timer": 0
            }
        }
        result = coordinator._check_any_mode_active(data)
        assert result is True
        
        # Test with expired timer (more than 10 minutes ago)
        data = {
            "tracker_456": {
                "find_timer": current_time - 700000,  # More than 10 minutes ago
                "light_timer": 0,
                "alarm_timer": 0
            }
        }
        result = coordinator._check_any_mode_active(data)
        assert result is False

    def test_update_polling_interval(
        self, 
        coordinator: PawfitDataUpdateCoordinator
    ) -> None:
        """Test polling interval updates."""
        # Test switching to fast polling
        import time
        current_time = time.time() * 1000
        
        data_with_active_mode = {
            "tracker_456": {
                "find_timer": current_time - 30000,  # 30 seconds ago
                "light_timer": 0,
                "alarm_timer": 0
            }
        }
        
        coordinator._update_polling_interval(data_with_active_mode)
        assert coordinator.update_interval == timedelta(seconds=1)
        
        # Test switching back to default polling
        data_with_no_active_mode = {
            "tracker_456": {
                "find_timer": 0,
                "light_timer": 0,
                "alarm_timer": 0
            }
        }
        
        coordinator._update_polling_interval(data_with_no_active_mode)
        assert coordinator.update_interval == timedelta(seconds=60)

    @pytest.mark.asyncio
    async def test_set_fast_polling(
        self, 
        coordinator: PawfitDataUpdateCoordinator
    ) -> None:
        """Test manual fast polling activation."""
        # Initially should be default interval
        assert coordinator.update_interval == timedelta(seconds=60)
        
        await coordinator.async_set_fast_polling()
        assert coordinator.update_interval == timedelta(seconds=1)
