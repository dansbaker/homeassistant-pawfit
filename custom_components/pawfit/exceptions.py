"""Custom exceptions for Pawfit integration."""
from __future__ import annotations


class PawfitError(Exception):
    """Base exception for Pawfit integration."""


class PawfitAuthenticationError(PawfitError):
    """Exception raised when authentication fails."""


class PawfitApiError(PawfitError):
    """Exception raised when API request fails."""


class PawfitConnectionError(PawfitError):
    """Exception raised when connection to Pawfit API fails."""


class PawfitInvalidResponseError(PawfitError):
    """Exception raised when API returns invalid response."""


class PawfitRateLimitError(PawfitError):
    """Exception raised when API rate limit is exceeded."""


class PawfitNotAuthenticatedError(PawfitError):
    """Exception raised when client is not authenticated."""
