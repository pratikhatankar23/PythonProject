import json
from pathlib import Path

import pytest

from pageObjects.msmeLogin import MsmeLoginPage


PROJECT_ROOT = Path(__file__).resolve().parents[1]
TEST_DATA_PATH = PROJECT_ROOT / "TestData" / "msmeLogin.json"


def _load_login_data():
    with TEST_DATA_PATH.open(encoding="utf-8") as data_file:
        data = json.load(data_file)

    if not isinstance(data, list):
        raise ValueError("msmeLogin.json must contain a list of login data dictionaries.")

    return data


@pytest.mark.parametrize(
    "login_data",
    _load_login_data(),
    ids=lambda data: data.get("case_id", data.get("username", "msme_login")),
)
def test_msme_login(page, base_url, login_data):
    msme_login = MsmeLoginPage(page, base_url)
    msme_login.login(
        username=login_data["username"],
        password=login_data["password"],
        otp=login_data["otp"],
    )
