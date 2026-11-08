"""Protocol parsing, credential refresh, response cleanup and failure semantics."""

import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, Mock

import aiohttp
import pytest

from custom_components.pawfit.pawfit_api import (
    PawfitApiClient,
    calculate_api_sign,
    calculate_login_sign,
)
from custom_components.pawfit.exceptions import (
    PawfitApiError,
    PawfitAuthenticationError,
    PawfitConnectionError,
    PawfitInvalidResponseError,
    PawfitRateLimitError,
)


def response(payload=None, status=200, text=None):
    return SimpleNamespace(
        status=status,
        text=AsyncMock(return_value=text if text is not None else json.dumps(payload)),
        release=Mock(),
    )


@pytest.fixture
def api():
    session = SimpleNamespace(request=AsyncMock(), post=MagicMock())
    client = PawfitApiClient("private-user", "private-password", session)
    client._user_id = "user"
    client._token = "token"
    return client


def login_response(api, r):
    context = MagicMock()
    context.__aenter__.return_value = r
    context.__aexit__.return_value = False
    api._session.post.return_value = context


@pytest.mark.parametrize(
    "payload,status,expected",
    [
        ({"success": False}, 200, PawfitAuthenticationError),
        ({"success": True, "data": {}}, 200, PawfitInvalidResponseError),
        ({"success": True, "data": []}, 200, PawfitInvalidResponseError),
        ({}, 403, PawfitAuthenticationError),
        ({}, 429, PawfitRateLimitError),
        ({}, 503, PawfitApiError),
    ],
)
async def test_login_failures_are_typed_and_do_not_expose_body(
    api, payload, status, expected
):
    login_response(api, response(payload, status))
    with pytest.raises(expected) as err:
        await api.async_login()
    assert "private-" not in str(err.value)


async def test_login_connection_timeout_is_safe(api):
    api._session.post.side_effect = TimeoutError("PRIVATE URL")
    with pytest.raises(PawfitConnectionError, match="login connection failed"):
        await api.async_login()


async def test_login_stores_string_identifiers_and_counts_request(api):
    login_response(
        api, response({"success": True, "data": {"userId": 123, "sessionId": 456}})
    )
    assert await api.async_login() == {"userId": "123", "sessionId": "456"}
    assert api.requests_today == api.request_count == 1
    form = api._session.post.call_args.kwargs["data"]
    assert form["sign"] == calculate_login_sign(
        "private-user", "private-password", int(form["t"])
    )


@pytest.mark.parametrize("text", ["not-json", "[]", "null", "42"])
def test_invalid_json_is_not_success(api, text):
    with pytest.raises(PawfitInvalidResponseError):
        api._decode_json(text)


@pytest.mark.parametrize(
    "status,expected",
    [
        (401, PawfitAuthenticationError),
        (403, PawfitAuthenticationError),
        (429, PawfitRateLimitError),
        (500, PawfitApiError),
    ],
)
async def test_failed_requests_release_responses(api, status, expected):
    r = response({}, status)
    api._session.request.return_value = r
    api._async_reauthenticate = AsyncMock()
    with pytest.raises(expected):
        await api.async_get_locations(["1"])
    assert r.release.called
    assert api.request_count == (2 if status in (401, 403) else 1)


async def test_request_network_failure_is_sanitized(api):
    api._session.request.side_effect = aiohttp.ClientError("PRIVATE URL/token")
    with pytest.raises(PawfitConnectionError) as err:
        await api.async_get_trackers()
    assert "PRIVATE" not in str(err.value)


async def test_body_failure_always_releases_response(api):
    r = response({})
    r.text.side_effect = TimeoutError("PRIVATE")
    api._session.request.return_value = r
    with pytest.raises(PawfitConnectionError):
        await api.async_get_trackers()
    r.release.assert_called_once()


async def test_json_application_failure_and_malformed_body_release_response(api):
    for r in (
        response({"success": False, "data": "PRIVATE"}),
        response(text="PRIVATE bad json"),
    ):
        api._session.request.return_value = r
        with pytest.raises((PawfitApiError, PawfitInvalidResponseError)) as err:
            await api.async_get_trackers()
        assert "PRIVATE" not in str(err.value)
        r.release.assert_called_once()


async def test_already_refreshed_session_does_not_login_again(api):
    api._async_login_unlocked = AsyncMock()
    await api._async_reauthenticate("old-token")
    api._async_login_unlocked.assert_not_awaited()


def test_unauthenticated_signing_and_path_building_are_rejected(api):
    api._token = None
    with pytest.raises(PawfitAuthenticationError):
        api._get_sign()
    with pytest.raises(PawfitAuthenticationError):
        api._append_auth_to_url("https://example.invalid")


async def test_non_appended_path_and_signature_params(api):
    api._session.request.return_value = response({"success": True})
    await api._request_with_reauth(
        "GET",
        "https://example.invalid/",
        {},
        append_auth=False,
        params={"q": "v"},
        sign_params={"tracker": "7"},
    )
    args = api._session.request.call_args
    assert args.args[1] == "https://example.invalid/"
    assert args.kwargs["params"] == {
        "q": "v",
        "sign": calculate_api_sign("user", "token", tracker="7"),
    }


@pytest.mark.parametrize("alias", ["tracker", "tracker_id", "id", "trackerId"])
async def test_list_shaped_device_responses_accept_identifier_aliases(api, alias):
    record = {
        alias: "7",
        "name": "Test pet",
        "petId": 12,
        "state": {
            "location": {"latitude": 0, "longitude": 0, "utcDateTime": 123},
            "power": -80,
            "signal": -70,
        },
    }
    api._session.request.return_value = response(
        {"success": True, "data": [None, record, {"no": "id"}]}
    )
    assert (await api.async_get_trackers())[0]["tracker_id"] == "7"
    locations = await api.async_get_locations(["7"])
    assert locations["7"]["latitude"] == 0 and locations["7"]["last_update"] == 123


@pytest.mark.parametrize("payload", [None, 42, "bad"])
async def test_invalid_collection_shapes_raise(api, payload):
    api._session.request.return_value = response({"success": True, "data": payload})
    with pytest.raises(PawfitInvalidResponseError):
        await api.async_get_trackers()


async def test_invalid_device_records_are_ignored(api):
    api._session.request.return_value = response(
        {
            "success": True,
            "data": {
                "1": None,
                "2": {},
                "3": {"state": "bad"},
                "4": {"state": {"location": None}},
            },
        }
    )
    assert await api.async_get_trackers() == []
    assert list(await api.async_get_locations(["1", "2", "3", "4"])) == ["4"]


@pytest.mark.parametrize(
    "mode,field", [("find", "gps"), ("light", "light"), ("alarm", "speaker")]
)
@pytest.mark.parametrize("enabled", [False, True])
async def test_mode_commands_use_existing_protocol_and_respect_rejection(
    api, mode, field, enabled
):
    api._session.request.return_value = response({"success": False})
    assert not await getattr(
        api, f"async_{'start' if enabled else 'stop'}_{mode}_mode"
    )("7")
    call = api._session.request.call_args
    assert ("starttracking" if enabled else "stoptracking") in call.args[1]
    assert call.kwargs["params"][field] == "1"
    assert call.kwargs["params"]["sign"] == calculate_api_sign(
        "user", "token", tracker="7"
    )
    api._session.request.return_value = response(text="not an acknowledgement")
    with pytest.raises(PawfitInvalidResponseError):
        await getattr(api, f"async_{'start' if enabled else 'stop'}_{mode}_mode")("7")


@pytest.mark.parametrize(
    "ids,params", [(None, None), (["1", "2"], {"trackers": "1,2"})]
)
async def test_detailed_status_does_not_prebuild_authentication_path(api, ids, params):
    api._session.request.return_value = response({"success": True, "data": {"1": {}}})
    assert await api.async_get_detailed_status(ids) == {"1": {}}
    call = api._session.request.call_args
    assert call.args[1].endswith("/user/token")
    assert call.kwargs["params"].get("trackers") == (params or {}).get("trackers")


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"data": {"activities": None}},
        {"data": {"activities": [{"hourlyStats": [{"calorie": "nan"}]}]}},
        {"data": {"activities": [{"hourlyStats": [{"pace": -1}]}]}},
    ],
)
def test_invalid_activity_is_not_replaced_with_zero(api, payload):
    with pytest.raises(PawfitInvalidResponseError):
        api._compile_daily_activity_stats(payload)


@pytest.mark.parametrize("body", ["invalid base64!", "eA", "eA=="])
async def test_corrupt_activity_zip_releases_response(api, body):
    r = response(text=body)
    api._session.request.return_value = r
    with pytest.raises(PawfitInvalidResponseError):
        await api.async_get_activity_stats("1")
    r.release.assert_called_once()
