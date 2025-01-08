from unittest.mock import patch

import pytest
import requests

from quantalogic.utils.check_version import check_latest


def test_check_latest_up_to_date():
    with patch('quantalogic.utils.check_version.get_version', return_value='1.2.3'), \
         patch('requests.get') as mock_get:
        mock_get.return_value.json.return_value = {'info': {'version': '1.2.3'}}
        mock_get.return_value.raise_for_status.return_value = None
        assert check_latest() is True

def test_check_latest_outdated():
    with patch('quantalogic.utils.check_version.get_version', return_value='1.2.2'), \
         patch('requests.get') as mock_get:
        mock_get.return_value.json.return_value = {'info': {'version': '1.2.3'}}
        mock_get.return_value.raise_for_status.return_value = None
        assert check_latest() is False

def test_check_latest_network_error():
    with patch('quantalogic.utils.check_version.get_version', return_value='1.2.3'), \
         patch('requests.get') as mock_get:
        mock_get.side_effect = requests.RequestException('Network error')
        assert check_latest() is False

def test_check_latest_invalid_response():
    with patch('quantalogic.utils.check_version.get_version', return_value='1.2.3'), \
         patch('requests.get') as mock_get:
        mock_get.return_value.json.return_value = {}
        mock_get.return_value.raise_for_status.return_value = None
        assert check_latest() is False
