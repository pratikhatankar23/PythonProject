import json
from pathlib import Path

import pytest

from pageObjects.msmeLogin import MsmeLoginPage
from pageObjects.rtgsRegPayeeOnetime import RtgsRegPayeeOnetimePage


PROJECT_ROOT = Path(__file__).resolve().parents[1]
LOGIN_DATA_PATH = PROJECT_ROOT / "TestData" / "msmeLogin.json"
RTGS_DATA_PATH = PROJECT_ROOT / "TestData" / "rtgsRegPayeeOnetime.json"


def _load_json_data(path):
    with path.open(encoding="utf-8") as data_file:
        data = json.load(data_file)

    if isinstance(data, dict) and isinstance(data.get("data"), list):
        return data["data"]

    if not isinstance(data, list):
        raise ValueError(
            f"{path.name} must contain a list or a dictionary with a data list."
        )

    return data


@pytest.mark.parametrize(
    "login_data",
    _load_json_data(LOGIN_DATA_PATH),
    ids=lambda data: data.get("case_id", data.get("username", "msme_login")),
)
@pytest.mark.parametrize(
    "rtgs_data",
    _load_json_data(RTGS_DATA_PATH),
    ids=lambda data: data.get("case_id", data.get("payeename", "rtgs_reg_payee")),
)
def test_rtgs_registered_payee_onetime(page, base_url, login_data, rtgs_data):
    msme_login = MsmeLoginPage(page, base_url)
    msme_login.login(
        username=login_data["username"],
        password=login_data["password"],
        otp=login_data["otp"],
    )

    rtgs_payment = RtgsRegPayeeOnetimePage(page)
    rtgs_payment.rtgs_registered_payee_onetime(rtgs_data)
