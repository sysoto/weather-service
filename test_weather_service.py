import json
import unittest
from unittest.mock import patch, MagicMock
import requests

import weather_service


class TestGeocode(unittest.TestCase):
    @patch("weather_service.requests.get")
    def test_geocode_direct_hit(self, mock_get):
        """Returns (lat, lon) when the full location string matches immediately."""
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "results": [{"latitude": 40.7128, "longitude": -74.0060}]
        }
        mock_get.return_value = mock_resp

        coords = weather_service.geocode("New York")
        self.assertEqual(coords, (40.7128, -74.0060))
        self.assertEqual(mock_get.call_count, 1)

    @patch("weather_service.requests.get")
    def test_geocode_comma_fallback(self, mock_get):
        """Retries with just the city part before the comma if 'City, ST' fails."""
        empty_resp = MagicMock()
        empty_resp.json.return_value = {}

        success_resp = MagicMock()
        success_resp.json.return_value = {
            "results": [{"latitude": 38.8951, "longitude": -77.0364}]
        }

        mock_get.side_effect = [empty_resp, success_resp]

        coords = weather_service.geocode("Washington, DC")
        self.assertEqual(coords, (38.8951, -77.0364))
        self.assertEqual(mock_get.call_count, 2)
        # Verify second call stripped the state
        _, kwargs = mock_get.call_args_list[1]
        self.assertEqual(kwargs["params"]["name"], "Washington")

    @patch("weather_service.requests.get")
    def test_geocode_not_found(self, mock_get):
        """Returns None when no results are returned."""
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"results": []}
        mock_get.return_value = mock_resp

        self.assertIsNone(weather_service.geocode("Nowhereville"))

    @patch("weather_service.requests.get")
    def test_geocode_request_exception(self, mock_get):
        """Returns None if a network error occurs."""
        mock_get.side_effect = requests.RequestException("Network failure")
        self.assertIsNone(weather_service.geocode("Chicago"))


class TestFetchTemperature(unittest.TestCase):
    @patch("weather_service.requests.get")
    def test_fetch_temperature_fahrenheit(self, mock_get):
        """Maps unit 'F' to 'fahrenheit' and extracts temperature."""
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"current_weather": {"temperature": 72.5}}
        mock_get.return_value = mock_resp

        temp = weather_service.fetch_temperature(40.71, -74.00, "F")
        self.assertEqual(temp, 72.5)
        _, kwargs = mock_get.call_args
        self.assertEqual(kwargs["params"]["temperature_unit"], "fahrenheit")

    @patch("weather_service.requests.get")
    def test_fetch_temperature_celsius(self, mock_get):
        """Maps unit 'C' to 'celsius' and extracts temperature."""
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"current_weather": {"temperature": 22.5}}
        mock_get.return_value = mock_resp

        temp = weather_service.fetch_temperature(40.71, -74.00, "C")
        self.assertEqual(temp, 22.5)
        _, kwargs = mock_get.call_args
        self.assertEqual(kwargs["params"]["temperature_unit"], "celsius")

    @patch("weather_service.requests.get")
    def test_fetch_temperature_failure(self, mock_get):
        """Returns None when the API raises an error or lacks expected keys."""
        mock_get.side_effect = requests.Timeout("Timed out")
        self.assertIsNone(weather_service.fetch_temperature(40.71, -74.00, "F"))


class TestHandleRequest(unittest.TestCase):
    def _encode(self, payload):
        return json.dumps(payload).encode("utf-8")

    def test_invalid_json(self):
        res = weather_service.handle_request(b"not-valid-json{")
        self.assertEqual(
            res, {"success": False, "error": "Request must be valid JSON."}
        )

    def test_non_dict_json(self):
        res = weather_service.handle_request(self._encode(["a", "list"]))
        self.assertEqual(
            res, {"success": False, "error": "Request must be a JSON object."}
        )

    def test_unknown_action(self):
        res = weather_service.handle_request(
            self._encode({"action": "get_forecast", "location": "NYC", "unit": "F"})
        )
        self.assertEqual(
            res, {"success": False, "error": "Unknown action 'get_forecast'."}
        )

    def test_missing_or_empty_location(self):
        for bad_loc in ("", "   ", None, 123):
            res = weather_service.handle_request(
                self._encode(
                    {"action": "get_temperature", "location": bad_loc, "unit": "F"}
                )
            )
            self.assertEqual(
                res, {"success": False, "error": "Location is required."}
            )

    def test_invalid_unit(self):
        for bad_unit in ("K", "", None, 42):
            res = weather_service.handle_request(
                self._encode(
                    {"action": "get_temperature", "location": "NYC", "unit": bad_unit}
                )
            )
            self.assertEqual(
                res, {"success": False, "error": "Unit must be 'F' or 'C'."}
            )

    @patch("weather_service.geocode", return_value=None)
    def test_location_not_found(self, mock_geocode):
        res = weather_service.handle_request(
            self._encode(
                {"action": "get_temperature", "location": "Atlantis", "unit": "F"}
            )
        )
        self.assertEqual(
            res, {"success": False, "error": "Location was not found."}
        )
        mock_geocode.assert_called_once_with("Atlantis")

    @patch("weather_service.fetch_temperature", return_value=None)
    @patch("weather_service.geocode", return_value=(40.71, -74.00))
    def test_weather_data_unavailable(self, mock_geocode, mock_fetch):
        res = weather_service.handle_request(
            self._encode(
                {"action": "get_temperature", "location": "New York", "unit": "C"}
            )
        )
        self.assertEqual(
            res,
            {"success": False, "error": "Weather data is unavailable right now."},
        )

    @patch("weather_service.fetch_temperature", return_value=68.4)
    @patch("weather_service.geocode", return_value=(47.6062, -122.3321))
    def test_successful_request_normalizes_input(self, mock_geocode, mock_fetch):
        """Trims location whitespace and uppercases lowercase 'f'/'c' units."""
        res = weather_service.handle_request(
            self._encode(
                {
                    "action": "get_temperature",
                    "location": "  Seattle, WA  ",
                    "unit": "f",
                }
            )
        )
        self.assertEqual(
            res,
            {
                "success": True,
                "location": "Seattle, WA",
                "temperature": 68.4,
                "unit": "F",
            },
        )
        mock_geocode.assert_called_once_with("Seattle, WA")
        mock_fetch.assert_called_once_with(47.6062, -122.3321, "F")


if __name__ == "__main__":
    unittest.main()
