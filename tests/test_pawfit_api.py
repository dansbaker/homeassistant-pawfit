"""Tests for Pawfit API client."""
from __future__ import annotations

import json
from typing import Any, AsyncGenerator, Dict
from unittest.mock import AsyncMock, MagicMock, patch

import aiohttp
import pytest
from aioresponses import aioresponses

from custom_components.pawfit.const import BASE_URL, USER_AGENT
from custom_components.pawfit.exceptions import (
    PawfitApiError,
    PawfitAuthenticationError,
    PawfitConnectionError,
    PawfitInvalidResponseError,
)
from custom_components.pawfit.pawfit_api import PawfitApiClient


class TestPawfitApiClient:
    """Test the PawfitApiClient class."""

    @pytest.fixture
    async def api_client(self) -> AsyncGenerator[PawfitApiClient, None]:
        """Create an API client instance for testing."""
        session = aiohttp.ClientSession()
        client = PawfitApiClient("test@example.com", "test_password", session)
        yield client
        await session.close()

    @pytest.mark.asyncio
    @pytest.mark.asyncio
    async def test_init(self) -> None:
        """Test API client initialization."""
        session = aiohttp.ClientSession()
        client = PawfitApiClient("test@example.com", "test_password", session)
        
        assert client._username == "test@example.com"
        assert client._password == "test_password"
        assert client._session == session
        assert client._token is None
        assert client._user_id is None
        
        await session.close()

    @pytest.mark.asyncio
    @pytest.mark.asyncio
    async def test_successful_login(self, api_client: PawfitApiClient) -> None:
        """Test successful login."""
        with aioresponses() as mock_resp:
            mock_resp.get(
                f"{BASE_URL}login/1/1",
                payload={
                    "success": True,
                    "data": {
                        "userId": "test_user_123",
                        "sessionId": "test_session_456"
                    }
                },
                status=200
            )
            
            result = await api_client.async_login()
            
            assert result["userId"] == "test_user_123"
            assert result["sessionId"] == "test_session_456"
            assert api_client._user_id == "test_user_123"
            assert api_client._token == "test_session_456"

    @pytest.mark.asyncio
    async def test_login_authentication_error(self, api_client: PawfitApiClient) -> None:
        """Test login with authentication error."""
        with aioresponses() as mock_resp:
            mock_resp.get(
                f"{BASE_URL}login/1/1",
                status=401
            )
            
            with pytest.raises(PawfitAuthenticationError):
                await api_client.async_login()

    @pytest.mark.asyncio
    async def test_login_invalid_response(self, api_client: PawfitApiClient) -> None:
        """Test login with invalid JSON response."""
        with aioresponses() as mock_resp:
            mock_resp.get(
                f"{BASE_URL}login/1/1",
                body="invalid json",
                status=200
            )
            
            with pytest.raises(PawfitInvalidResponseError):
                await api_client.async_login()

    @pytest.mark.asyncio
    async def test_login_missing_credentials(self, api_client: PawfitApiClient) -> None:
        """Test login with missing credentials in response."""
        with aioresponses() as mock_resp:
            mock_resp.get(
                f"{BASE_URL}login/1/1",
                payload={
                    "success": True,
                    "data": {}
                },
                status=200
            )
            
            with pytest.raises(PawfitAuthenticationError):
                await api_client.async_login()

    @pytest.mark.asyncio
    async def test_connection_error(self, api_client: PawfitApiClient) -> None:
        """Test connection error during login."""
        with aioresponses() as mock_resp:
            mock_resp.get(
                f"{BASE_URL}login/1/1",
                exception=aiohttp.ClientError("Connection failed")
            )
            
            with pytest.raises(PawfitConnectionError):
                await api_client.async_login()

    @pytest.mark.asyncio
    async def test_get_trackers_success(self, api_client: PawfitApiClient) -> None:
        """Test successful tracker retrieval."""
        # First mock login
        api_client._user_id = "test_user_123"
        api_client._token = "test_session_456"
        
        with aioresponses() as mock_resp:
            mock_resp.get(
                f"{BASE_URL}listpetinvitee/1/1/test_user_123/test_session_456",
                payload={
                    "success": True,
                    "data": {
                        "tracker_456": {
                            "name": "Buddy",
                            "petId": "pet_123"
                        }
                    }
                },
                status=200
            )
            
            trackers = await api_client.async_get_trackers()
            
            assert len(trackers) == 1
            assert trackers[0]["name"] == "Buddy"
            assert trackers[0]["petId"] == "pet_123"
            assert trackers[0]["tracker_id"] == "tracker_456"

    @pytest.mark.asyncio
    async def test_get_trackers_not_authenticated(self, api_client: PawfitApiClient) -> None:
        """Test tracker retrieval when not authenticated."""
        with aioresponses() as mock_resp:
            # Mock login call
            mock_resp.get(
                f"{BASE_URL}login/1/1",
                payload={
                    "success": True,
                    "data": {
                        "userId": "test_user_123",
                        "sessionId": "test_session_456"
                    }
                },
                status=200
            )
            
            # Mock trackers call
            mock_resp.get(
                f"{BASE_URL}listpetinvitee/1/1/test_user_123/test_session_456",
                payload={
                    "success": True,
                    "data": {
                        "tracker_456": {
                            "name": "Buddy",
                            "petId": "pet_123"
                        }
                    }
                },
                status=200
            )
            
            trackers = await api_client.async_get_trackers()
            
            assert len(trackers) == 1
            assert api_client._user_id == "test_user_123"
            assert api_client._token == "test_session_456"

    @pytest.mark.asyncio
    async def test_get_locations_success(self, api_client: PawfitApiClient) -> None:
        """Test successful location retrieval."""
        # Set up authenticated state
        api_client._user_id = "test_user_123"
        api_client._token = "test_session_456"
        
        with aioresponses() as mock_resp:
            mock_resp.get(
                f"{BASE_URL}getlocationcaches/1/1/test_user_123/test_session_456?trackers=tracker_456",
                payload={
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
                },
                status=200
            )
            
            locations = await api_client.async_get_locations(["tracker_456"])
            
            assert "tracker_456" in locations
            location = locations["tracker_456"]
            assert location["latitude"] == 40.7128
            assert location["longitude"] == -74.0060
            assert location["accuracy"] == 10.0
            assert location["battery"] == 85
            assert location["signal"] == -70

    @pytest.mark.asyncio
    async def test_append_auth_to_url_not_authenticated(self, api_client: PawfitApiClient) -> None:
        """Test URL authentication when not authenticated."""
        from custom_components.pawfit.exceptions import PawfitNotAuthenticatedError
        
        with pytest.raises(PawfitNotAuthenticatedError):
            api_client._append_auth_to_url("http://example.com/api")

    @pytest.mark.asyncio
    async def test_append_auth_to_url_authenticated(self, api_client: PawfitApiClient) -> None:
        """Test URL authentication when authenticated."""
        api_client._user_id = "test_user_123"
        api_client._token = "test_session_456"
        
        result = api_client._append_auth_to_url("http://example.com/api")
        assert result == "http://example.com/api/test_user_123/test_session_456"
        
        # Test with trailing slash
        result = api_client._append_auth_to_url("http://example.com/api/")
        assert result == "http://example.com/api/test_user_123/test_session_456"

    @pytest.mark.asyncio
    async def test_start_find_mode_success(self, api_client: PawfitApiClient) -> None:
        """Test successful find mode start."""
        api_client._user_id = "test_user_123"
        api_client._token = "test_session_456"
        
        with aioresponses() as mock_resp:
            mock_resp.get(
                f"{BASE_URL}starttracking/1/1/test_user_123/test_session_456",
                payload={"success": True},
                status=200
            )
            
            result = await api_client.async_start_find_mode("tracker_456")
            assert result is True

    @pytest.mark.asyncio
    async def test_start_find_mode_failure(self, api_client: PawfitApiClient) -> None:
        """Test find mode start failure."""
        api_client._user_id = "test_user_123"
        api_client._token = "test_session_456"
        
        with aioresponses() as mock_resp:
            mock_resp.get(
                f"{BASE_URL}starttracking/1/1/test_user_123/test_session_456",
                status=500
            )
            
            result = await api_client.async_start_find_mode("tracker_456")
            assert result is False

    @pytest.mark.asyncio
    async def test_get_activity_stats_success(self, api_client: PawfitApiClient) -> None:
        """Test successful activity stats retrieval."""
        import base64
        import zlib
        
        api_client._user_id = "test_user_123"
        api_client._token = "test_session_456"
        
        # Create mock compressed response
        activity_data = {
            "success": True,
            "data": {
                "activities": [
                    {
                        "hourlyStats": [
                            {"calorie": 10.5, "active": 0.5, "pace": 150},
                            {"calorie": 15.2, "active": 0.8, "pace": 200}
                        ]
                    }
                ]
            }
        }
        
        json_data = json.dumps(activity_data).encode('utf-8')
        compressed_data = zlib.compress(json_data)
        encoded_data = base64.urlsafe_b64encode(compressed_data).decode('utf-8')
        
        with aioresponses() as mock_resp:
            mock_resp.get(
                f"{BASE_URL}getactivitystatzip/1/1/test_user_123/test_session_456",
                body=encoded_data,
                status=200
            )
            
            stats = await api_client.async_get_activity_stats("tracker_456")
            
            assert stats["total_steps"] == 350  # 150 + 200
            assert stats["total_calories"] == 25.7  # 10.5 + 15.2
            assert stats["total_active_hours"] == 1.3  # 0.5 + 0.8
