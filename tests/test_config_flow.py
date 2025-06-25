"""Tests for Pawfit config flow."""
from __future__ import annotations

from typing import Any, Dict, Generator
from unittest.mock import AsyncMock, patch

import pytest
from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME

from custom_components.pawfit.config_flow import PawfitConfigFlow
from custom_components.pawfit.const import DOMAIN
from custom_components.pawfit.exceptions import (
    PawfitAuthenticationError,
    PawfitConnectionError,
)


class TestPawfitConfigFlow:
    """Test the Pawfit config flow."""

    @pytest.fixture
    def mock_setup_entry(self) -> Generator[AsyncMock, None, None]:
        """Mock setting up a config entry."""
        with patch(
            "custom_components.pawfit.async_setup_entry", return_value=True
        ) as mock_setup:
            yield mock_setup

    @pytest.mark.asyncio
    async def test_form_user_success(self, hass: Any, mock_setup_entry: AsyncMock) -> None:
        """Test successful user form submission."""
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        
        assert result["type"] == FlowResultType.FORM
        assert result["errors"] == {}

        with patch(
            "custom_components.pawfit.config_flow.PawfitApiClient"
        ) as mock_api_client:
            mock_client_instance = AsyncMock()
            mock_api_client.return_value = mock_client_instance
            mock_client_instance.async_login.return_value = {
                "userId": "test_user_123",
                "sessionId": "test_session_456"
            }
            
            result2 = await hass.config_entries.flow.async_configure(
                result["flow_id"],
                {
                    CONF_USERNAME: "test@example.com",
                    CONF_PASSWORD: "test_password",
                },
            )

        assert result2["type"] == FlowResultType.CREATE_ENTRY
        assert result2["title"] == "Pawfit Account"
        assert result2["data"] == {
            CONF_USERNAME: "test@example.com",
            CONF_PASSWORD: "test_password",
            "userId": "test_user_123",
            "sessionId": "test_session_456",
        }

    @pytest.mark.asyncio
    async def test_form_invalid_auth(self, hass: Any) -> None:
        """Test invalid authentication."""
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

        with patch(
            "custom_components.pawfit.config_flow.PawfitApiClient"
        ) as mock_api_client:
            mock_client_instance = AsyncMock()
            mock_api_client.return_value = mock_client_instance
            mock_client_instance.async_login.side_effect = PawfitAuthenticationError(
                "Invalid credentials"
            )
            
            result2 = await hass.config_entries.flow.async_configure(
                result["flow_id"],
                {
                    CONF_USERNAME: "test@example.com",
                    CONF_PASSWORD: "wrong_password",
                },
            )

        assert result2["type"] == FlowResultType.FORM
        assert result2["errors"] == {"base": "invalid_auth"}

    @pytest.mark.asyncio
    async def test_form_connection_error(self, hass: Any) -> None:
        """Test connection error."""
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

        with patch(
            "custom_components.pawfit.config_flow.PawfitApiClient"
        ) as mock_api_client:
            mock_client_instance = AsyncMock()
            mock_api_client.return_value = mock_client_instance
            mock_client_instance.async_login.side_effect = PawfitConnectionError(
                "Connection failed"
            )
            
            result2 = await hass.config_entries.flow.async_configure(
                result["flow_id"],
                {
                    CONF_USERNAME: "connection_error@example.com",
                    CONF_PASSWORD: "test_password",
                },
            )

        assert result2["type"] == FlowResultType.FORM
        assert result2["errors"] == {"base": "cannot_connect"}

    @pytest.mark.asyncio
    async def test_form_unknown_error(self, hass: Any) -> None:
        """Test unknown error."""
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

        with patch(
            "custom_components.pawfit.config_flow.PawfitApiClient"
        ) as mock_api_client:
            mock_client_instance = AsyncMock()
            mock_api_client.return_value = mock_client_instance
            mock_client_instance.async_login.side_effect = Exception("Unexpected error")
            
            result2 = await hass.config_entries.flow.async_configure(
                result["flow_id"],
                {
                    CONF_USERNAME: "unknown_error@example.com",
                    CONF_PASSWORD: "test_password",
                },
            )

        assert result2["type"] == FlowResultType.FORM
        assert result2["errors"] == {"base": "unknown"}
