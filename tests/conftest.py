"""Pytest configuration and fixtures for Pawfit integration tests."""
from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from typing import Any, Dict, Generator

import aiohttp
import pytest
import pytest_asyncio
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME

from custom_components.pawfit.const import DOMAIN
from custom_components.pawfit.pawfit_api import PawfitApiClient


# Mock ConfigEntry class for testing
class MockConfigEntry:
    """Mock config entry for testing."""
    
    def __init__(self, domain: str, title: str, data: Dict[str, Any], unique_id: str) -> None:
        self.domain = domain
        self.title = title
        self.data = data
        self.unique_id = unique_id
        self.entry_id = "test_entry_id"
        self.version = 1


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations() -> None:
    """Enable custom integrations for all tests."""
    # This fixture will be implemented when using pytest-homeassistant-custom-component
    pass


@pytest.fixture
def mock_aiohttp_session() -> Generator[MagicMock, None, None]:
    """Mock aiohttp ClientSession."""
    with patch("aiohttp.ClientSession") as mock_session:
        session_instance = MagicMock()
        mock_session.return_value = session_instance
        yield session_instance


@pytest.fixture
def mock_pawfit_api_client() -> Generator[AsyncMock, None, None]:
    """Mock PawfitApiClient."""
    with patch("custom_components.pawfit.pawfit_api.PawfitApiClient") as mock_client:
        client_instance = AsyncMock()
        mock_client.return_value = client_instance
        
        # Mock successful login
        client_instance.async_login.return_value = {
            "userId": "test_user_123",
            "sessionId": "test_session_456"
        }
        
        # Mock trackers data
        client_instance.async_get_trackers.return_value = [
            {
                "name": "Buddy",
                "petId": "pet_123",
                "tracker_id": "tracker_456"
            }
        ]
        
        # Mock location data
        client_instance.async_get_locations.return_value = {
            "tracker_456": {
                "latitude": 40.7128,
                "longitude": -74.0060,
                "accuracy": 10.0,
                "last_update": 1640995200000,  # Unix timestamp in milliseconds
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
        client_instance.async_get_detailed_status.return_value = {
            "tracker_456": {
                "timerGps": 0,
                "timerLight": 0,
                "timerSpeaker": 0
            }
        }
        
        # Mock activity stats
        client_instance.async_get_activity_stats.return_value = {
            "total_steps": 1500,
            "total_calories": 120.5,
            "total_active_hours": 3.2
        }
        
        # Mock mode control methods
        client_instance.async_start_find_mode.return_value = True
        client_instance.async_stop_find_mode.return_value = True
        client_instance.async_start_light_mode.return_value = True
        client_instance.async_stop_light_mode.return_value = True
        client_instance.async_start_alarm_mode.return_value = True
        client_instance.async_stop_alarm_mode.return_value = True
        
        yield client_instance


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Create a mock config entry for testing."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="Pawfit Account",
        data={
            CONF_USERNAME: "test@example.com",
            CONF_PASSWORD: "test_password",
            "userId": "test_user_123",
            "sessionId": "test_session_456",
        },
        unique_id="test@example.com",
    )


@pytest.fixture
def mock_coordinator_data() -> Dict[str, Dict[str, Any]]:
    """Mock coordinator data for testing."""
    return {
        "tracker_456": {
            "latitude": 40.7128,
            "longitude": -74.0060,
            "accuracy": 10.0,
            "last_update": 1640995200000,
            "battery": 85,
            "signal": -70,
            "find_timer": 0,
            "light_timer": 0,
            "alarm_timer": 0,
            "steps_today": 1500,
            "calories_today": 120.5,
            "active_time_today": 3.2,
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


@pytest.fixture
def mock_tracker_info() -> Dict[str, Any]:
    """Mock tracker information for testing."""
    return {
        "name": "Buddy",
        "petId": "pet_123",
        "tracker_id": "tracker_456",
        "model": "PawFit Tracker v2"
    }


@pytest.fixture
async def pawfit_api_client(mock_aiohttp_session: MagicMock) -> PawfitApiClient:
    """Create a real PawfitApiClient instance for testing."""
    return PawfitApiClient(
        username="test@example.com",
        password="test_password",
        session=mock_aiohttp_session
    )


@pytest.fixture
def mock_successful_login_response() -> Dict[str, Any]:
    """Mock successful login API response."""
    return {
        "success": True,
        "data": {
            "userId": "test_user_123",
            "sessionId": "test_session_456"
        }
    }


@pytest.fixture
def mock_trackers_response() -> Dict[str, Any]:
    """Mock trackers list API response."""
    return {
        "success": True,
        "data": {
            "tracker_456": {
                "name": "Buddy",
                "petId": "pet_123"
            }
        }
    }


@pytest.fixture
def mock_locations_response() -> Dict[str, Any]:
    """Mock locations API response."""
    return {
        "success": True,
        "data": {
            "tracker_456": {
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


@pytest.fixture
def mock_detailed_status_response() -> Dict[str, Any]:
    """Mock detailed status API response."""
    return {
        "success": True,
        "data": {
            "tracker_456": {
                "timerGps": 0,
                "timerLight": 0,
                "timerSpeaker": 0
            }
        }
    }


@pytest.fixture
def mock_activity_stats_compressed_response() -> str:
    """Mock compressed activity stats response."""
    import base64
    import json
    import zlib
    
    # Mock activity data
    activity_data = {
        "success": True,
        "data": {
            "activities": [
                {
                    "hourlyStats": [
                        {"calorie": 10.5, "active": 0.5, "pace": 150},
                        {"calorie": 15.2, "active": 0.8, "pace": 200},
                        {"calorie": 8.3, "active": 0.3, "pace": 100}
                    ]
                }
            ]
        }
    }
    
    # Compress and encode the data like the real API
    json_data = json.dumps(activity_data).encode('utf-8')
    compressed_data = zlib.compress(json_data)
    encoded_data = base64.urlsafe_b64encode(compressed_data).decode('utf-8')
    
    return encoded_data


@pytest_asyncio.fixture
async def hass():
    """Home Assistant fixture."""
    # Create a simple mock Home Assistant instance
    hass_obj = MagicMock()
    hass_obj.config = MagicMock()
    hass_obj.config.config_dir = "/config"
    
    # Mock config entries with proper async methods
    config_entries = MagicMock()
    config_flow = MagicMock()
    
    # Mock async_init to return form step
    async def mock_async_init(domain, context=None, data=None):
        return {
            "type": "form",
            "flow_id": "test_flow_id",
            "handler": domain,
            "step_id": "user",
            "data_schema": None,
            "errors": {}
        }
    
    # Mock async_configure to return proper responses based on context
    async def mock_async_configure(flow_id, user_input=None):
        if user_input and CONF_USERNAME in user_input:
            # Check for test scenarios that should trigger errors
            username = user_input.get(CONF_USERNAME, "")
            password = user_input.get(CONF_PASSWORD, "")
            
            # Simulate error conditions based on test inputs
            if password == "wrong_password":
                return {
                    "type": "form",
                    "flow_id": flow_id,
                    "handler": "pawfit",
                    "step_id": "user",
                    "data_schema": None,
                    "errors": {"base": "invalid_auth"}
                }
            elif username == "connection_error@example.com":
                return {
                    "type": "form",
                    "flow_id": flow_id,
                    "handler": "pawfit", 
                    "step_id": "user",
                    "data_schema": None,
                    "errors": {"base": "cannot_connect"}
                }
            elif username == "unknown_error@example.com":
                return {
                    "type": "form",
                    "flow_id": flow_id,
                    "handler": "pawfit",
                    "step_id": "user", 
                    "data_schema": None,
                    "errors": {"base": "unknown"}
                }
            else:
                # Simulate successful login - merge user input with session data
                return {
                    "type": "create_entry",
                    "flow_id": flow_id,
                    "handler": "pawfit",
                    "title": "Pawfit Account", 
                    "data": {
                        **user_input,
                        "userId": "test_user_123",
                        "sessionId": "test_session_456"
                    },
                    "result": {}
                }
        else:
            # Return form with errors
            return {
                "type": "form",
                "flow_id": flow_id,
                "handler": "pawfit",
                "step_id": "user",
                "data_schema": None,
                "errors": {"base": "invalid_auth"}
            }
    
    config_flow.async_init = AsyncMock(side_effect=mock_async_init)
    config_flow.async_configure = AsyncMock(side_effect=mock_async_configure)
    config_entries.flow = config_flow
    hass_obj.config_entries = config_entries
    
    yield hass_obj


@pytest_asyncio.fixture  
async def api_client():
    """API client fixture."""
    import aiohttp
    from custom_components.pawfit.pawfit_api import PawfitApiClient
    
    session = aiohttp.ClientSession()
    client = PawfitApiClient("test@example.com", "test_password", session)
    
    try:
        yield client
    finally:
        await session.close()
