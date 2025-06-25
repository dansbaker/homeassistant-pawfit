"""Basic framework tests to verify pytest setup is working."""
from __future__ import annotations

import pytest

from custom_components.pawfit.const import DOMAIN


class TestBasicFramework:
    """Test basic framework functionality."""

    def test_domain_constant(self) -> None:
        """Test that the domain constant is defined."""
        assert DOMAIN == "pawfit"

    def test_imports_work(self) -> None:
        """Test that basic imports work."""
        from custom_components.pawfit.pawfit_api import PawfitApiClient
        from custom_components.pawfit.exceptions import PawfitApiError
        
        assert PawfitApiClient is not None
        assert PawfitApiError is not None

    @pytest.mark.asyncio
    async def test_async_functionality(self) -> None:
        """Test that async functionality works."""
        import asyncio
        
        async def dummy_async_func():
            await asyncio.sleep(0.001)  # Very short sleep
            return "success"
        
        result = await dummy_async_func()
        assert result == "success"
