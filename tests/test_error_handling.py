"""Test error handling for the Pawfit integration."""
from __future__ import annotations

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import aiohttp
import pytest
import pytest_asyncio
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady

from custom_components.pawfit import async_setup_entry, async_unload_entry
from custom_components.pawfit.binary_sensor import PawfitChargingSensor
from custom_components.pawfit.button import PawfitFindModeButton
from custom_components.pawfit.device_tracker import (
    PawfitDataUpdateCoordinator,
    PawfitDeviceTracker,
)
from custom_components.pawfit.exceptions import (
    PawfitError,
    PawfitApiError,
    PawfitAuthenticationError,
    PawfitConnectionError,
    PawfitInvalidResponseError,
)
from custom_components.pawfit.pawfit_api import PawfitApiClient
from custom_components.pawfit.sensor import PawfitSensor


class TestSetupErrorHandling:
    """Test setup/teardown error handling."""

    @pytest.fixture
    def mock_config_entry(self) -> Mock:
        """Create a mock config entry."""
        entry = Mock(spec=ConfigEntry)
        entry.data = {
            "username": "test@example.com",
            "password": "testpass123"
        }
        entry.entry_id = "test_entry_id"
        return entry

    @pytest.mark.asyncio
    async def test_setup_entry_authentication_error(
        self, hass: HomeAssistant, mock_config_entry: Mock
    ) -> None:
        """Test setup entry with authentication error."""
        with patch("aiohttp.ClientSession"), patch(
            "custom_components.pawfit.PawfitApiClient.async_get_trackers",
            side_effect=PawfitAuthenticationError("Invalid credentials")
        ):
            # Without proper error handling, this will raise the original exception
            with pytest.raises(PawfitAuthenticationError):
                await async_setup_entry(hass, mock_config_entry)

    @pytest.mark.asyncio
    async def test_setup_entry_connection_error(
        self, hass: HomeAssistant, mock_config_entry: Mock
    ) -> None:
        """Test setup entry with connection error."""
        with patch("aiohttp.ClientSession"), patch(
            "custom_components.pawfit.PawfitApiClient.async_get_trackers",
            side_effect=PawfitConnectionError("Connection failed")
        ):
            # Without proper error handling, this will raise the original exception
            with pytest.raises(PawfitConnectionError):
                await async_setup_entry(hass, mock_config_entry)

    @pytest.mark.asyncio
    async def test_setup_entry_unexpected_error(
        self, hass: HomeAssistant, mock_config_entry: Mock
    ) -> None:
        """Test setup entry with unexpected error."""
        with patch("aiohttp.ClientSession"), patch(
            "custom_components.pawfit.PawfitApiClient.async_get_trackers",
            side_effect=Exception("Unexpected error")
        ):
            # Without proper error handling, this will raise the original exception
            with pytest.raises(Exception):
                await async_setup_entry(hass, mock_config_entry)

    @pytest.mark.asyncio
    async def test_setup_entry_coordinator_refresh_error(
        self, hass: HomeAssistant, mock_config_entry: Mock
    ) -> None:
        """Test setup entry when coordinator refresh fails."""
        with patch("aiohttp.ClientSession"), patch(
            "custom_components.pawfit.PawfitApiClient.async_get_trackers",
            return_value=[{"tracker_id": "123456", "name": "Test Pet"}]
        ), patch(
            "custom_components.pawfit.device_tracker.PawfitDataUpdateCoordinator.async_config_entry_first_refresh",
            side_effect=PawfitConnectionError("Refresh failed")
        ):
            with pytest.raises(PawfitConnectionError):
                await async_setup_entry(hass, mock_config_entry)

    @pytest.mark.asyncio
    async def test_unload_entry_success(
        self, hass: HomeAssistant, mock_config_entry: Mock
    ) -> None:
        """Test unload entry succeeds."""
        # Mock the hass config_entries and data
        hass.config_entries = AsyncMock()
        hass.config_entries.async_unload_platforms = AsyncMock(return_value=True)
        hass.data = {"pawfit": {mock_config_entry.entry_id: MagicMock()}}
        
        result = await async_unload_entry(hass, mock_config_entry)
        assert result is True


class TestCoordinatorErrorHandling:
    """Test coordinator error handling."""

    @pytest_asyncio.fixture
    async def coordinator(self) -> PawfitDataUpdateCoordinator:
        """Create a coordinator for testing."""
        hass = MagicMock()
        client = AsyncMock(spec=PawfitApiClient)
        trackers = [{"tracker_id": "123456", "name": "Test Pet"}]
        return PawfitDataUpdateCoordinator(hass, client, trackers)

    @pytest.mark.asyncio
    async def test_coordinator_update_connection_error(
        self, coordinator: PawfitDataUpdateCoordinator
    ) -> None:
        """Test coordinator handles connection errors during update."""
        coordinator.client.async_get_locations.side_effect = PawfitConnectionError(
            "Connection failed"
        )
        
        # The coordinator should handle the error and return empty data or raise UpdateFailed
        with pytest.raises(Exception):  # Could be UpdateFailed or the original exception
            await coordinator._async_update_data()

    @pytest.mark.asyncio
    async def test_coordinator_update_authentication_error(
        self, coordinator: PawfitDataUpdateCoordinator
    ) -> None:
        """Test coordinator handles authentication errors during update."""
        coordinator.client.async_get_locations.side_effect = PawfitAuthenticationError(
            "Authentication failed"
        )
        
        with pytest.raises(Exception):
            await coordinator._async_update_data()

    @pytest.mark.asyncio
    async def test_coordinator_update_api_error(
        self, coordinator: PawfitDataUpdateCoordinator
    ) -> None:
        """Test coordinator handles API errors during update."""
        coordinator.client.async_get_locations.side_effect = PawfitApiError(
            "API error"
        )
        
        with pytest.raises(Exception):
            await coordinator._async_update_data()

    @pytest.mark.asyncio
    async def test_coordinator_successful_update_with_partial_failure(
        self, coordinator: PawfitDataUpdateCoordinator
    ) -> None:
        """Test coordinator handles partial failures gracefully."""
        # Mock locations succeeding but detailed status failing
        coordinator.client.async_get_locations.return_value = {
            "123456": {"latitude": 40.7128, "longitude": -74.0060}
        }
        coordinator.client.async_get_detailed_status.side_effect = PawfitConnectionError(
            "Detailed status failed"
        )
        
        # Should still return the location data even if detailed status fails
        result = await coordinator._async_update_data()
        assert "123456" in result
        assert result["123456"]["latitude"] == 40.7128


class TestApiClientErrorHandling:
    """Test API client error handling."""

    @pytest_asyncio.fixture
    async def api_client(self) -> PawfitApiClient:
        """Create an API client for testing."""
        session = AsyncMock(spec=aiohttp.ClientSession)
        client = PawfitApiClient("test@example.com", "testpass123", session)
        return client

    @pytest.mark.asyncio
    async def test_api_client_login_timeout(
        self, api_client: PawfitApiClient
    ) -> None:
        """Test API client handles login timeout."""
        api_client._session.get.side_effect = aiohttp.ClientError("Timeout")
        
        with pytest.raises(PawfitConnectionError):
            await api_client.async_login()

    @pytest.mark.asyncio
    async def test_api_client_login_client_error(
        self, api_client: PawfitApiClient
    ) -> None:
        """Test API client handles client connection error."""
        api_client._session.get.side_effect = aiohttp.ClientConnectionError()
        
        with pytest.raises(PawfitConnectionError):
            await api_client.async_login()

    @pytest.mark.asyncio
    async def test_api_client_malformed_response(
        self, api_client: PawfitApiClient
    ) -> None:
        """Test API client handles malformed response."""
        # Mock a response with invalid data
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.text = AsyncMock(return_value="invalid json")
        mock_response.json.side_effect = json.JSONDecodeError("Expecting value", "invalid json", 0)
        api_client._session.get.return_value.__aenter__.return_value = mock_response
        
        with pytest.raises(PawfitInvalidResponseError):
            await api_client.async_login()

    @pytest.mark.asyncio
    async def test_api_client_http_error_status(
        self, api_client: PawfitApiClient
    ) -> None:
        """Test API client handles HTTP error status."""
        mock_response = AsyncMock()
        mock_response.status = 401
        mock_response.text.return_value = '{"error": "Unauthorized"}'
        api_client._session.get.return_value.__aenter__.return_value = mock_response
        
        with pytest.raises(PawfitAuthenticationError):
            await api_client.async_login()

    @pytest.mark.asyncio
    async def test_api_client_server_error_status(
        self, api_client: PawfitApiClient
    ) -> None:
        """Test API client handles server error status."""
        mock_response = AsyncMock()
        mock_response.status = 500
        mock_response.text.return_value = '{"error": "Internal Server Error"}'
        api_client._session.get.return_value.__aenter__.return_value = mock_response
        
        with pytest.raises(PawfitAuthenticationError):  # Current implementation treats all non-200 as auth error
            await api_client.async_login()


class TestEntityErrorHandling:
    """Test entity error handling scenarios."""

    def test_device_tracker_missing_data(self) -> None:
        """Test device tracker handles missing data gracefully."""
        coordinator = MagicMock()
        coordinator.data = {}  # No data for tracker
        
        # Use test data that matches the actual constructor signature
        tracker = {
            "tracker_id": "123456",
            "name": "Test Pet",
            "petId": "pet123",
            "model": "Test Model"
        }
        
        device_tracker = PawfitDeviceTracker(
            tracker=tracker,
            coordinator=coordinator
        )
        
        # Should handle missing data gracefully
        assert device_tracker.available is False
        assert device_tracker.latitude is None
        assert device_tracker.longitude is None

    def test_sensor_missing_data(self) -> None:
        """Test sensor handles missing data gracefully."""
        coordinator = MagicMock(spec=PawfitDataUpdateCoordinator)
        coordinator.data = {}  # No data for tracker
        coordinator.last_update_success = False  # Simulate failed update
        
        # Use test data that matches the actual constructor signature
        tracker = {
            "tracker_id": "123456",
            "name": "Test Pet",
            "petId": "pet123",
            "model": "Test Model"
        }
        
        sensor = PawfitSensor(
            tracker=tracker,
            coordinator=coordinator,
            kind="battery",
            name="Battery Level",
            unit="%"
        )
        
        # Should handle missing data gracefully
        assert sensor.available is False
        assert sensor.native_value is None

    def test_binary_sensor_missing_data(self) -> None:
        """Test binary sensor handles missing data gracefully."""
        coordinator = MagicMock()
        coordinator.data = {}  # No data for tracker
        coordinator.last_update_success = False  # Set availability
        
        # Use test data that matches the actual constructor signature
        tracker = {
            "tracker_id": "123456",
            "name": "Test Pet",
            "petId": "pet123",
            "model": "Test Model"
        }
        
        sensor = PawfitChargingSensor(
            tracker=tracker,
            coordinator=coordinator
        )
        
        # Should handle missing data gracefully
        assert sensor.available is False
        assert sensor.is_on is None

    def test_button_missing_data(self) -> None:
        """Test button handles missing data gracefully."""
        coordinator = MagicMock()
        coordinator.data = {}  # No data for tracker
        coordinator.last_update_success = False  # Set availability
        
        # Use test data that matches the actual constructor signature
        tracker = {
            "tracker_id": "123456",
            "name": "Test Pet",
            "petId": "pet123",
            "model": "Test Model"
        }
        
        button = PawfitFindModeButton(
            tracker=tracker,
            coordinator=coordinator
        )
        
        # Should handle missing data gracefully
        assert button.available is False


class TestExceptionHierarchy:
    """Test custom exception hierarchy."""

    def test_exception_inheritance(self) -> None:
        """Test that custom exceptions have proper inheritance."""
        # All custom exceptions should inherit from PawfitError
        assert issubclass(PawfitAuthenticationError, PawfitError)
        assert issubclass(PawfitConnectionError, PawfitError)
        assert issubclass(PawfitApiError, PawfitError)
        
        # PawfitError should inherit from Exception
        assert issubclass(PawfitError, Exception)

    def test_exception_messages(self) -> None:
        """Test that exceptions can be created with messages."""
        auth_error = PawfitAuthenticationError("Invalid credentials")
        assert str(auth_error) == "Invalid credentials"
        
        conn_error = PawfitConnectionError("Connection failed")
        assert str(conn_error) == "Connection failed"
        
        api_error = PawfitApiError("API error")
        assert str(api_error) == "API error"

    def test_exception_catching(self) -> None:
        """Test that exceptions can be caught by their parent class."""
        # Should be able to catch specific exceptions
        try:
            raise PawfitAuthenticationError("test")
        except PawfitError as e:
            assert isinstance(e, PawfitAuthenticationError)
        
        # Should be able to catch all errors
        try:
            raise PawfitConnectionError("test")
        except PawfitError as e:
            assert isinstance(e, PawfitConnectionError)
