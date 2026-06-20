import json
from pathlib import Path

import pytest

from pageObjects.internalSiPayment import InternalSiPaymentPage
from pageObjects.msmeLogin import MsmeLoginPage


PROJECT_ROOT = Path(__file__).resolve().parents[1]
LOGIN_DATA_PATH = PROJECT_ROOT / "TestData" / "msmeLogin.json"
INTERNAL_SI_DATA_PATH = PROJECT_ROOT / "TestData" / "internalSiPayment.json"


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
    "internal_si_data",
    _load_json_data(INTERNAL_SI_DATA_PATH),
    ids=lambda data: data.get("case_id", data.get("payeename", "internal_si_payment")),
)
def test_internal_si_payment(page, base_url, login_data, internal_si_data):
    msme_login = MsmeLoginPage(page, base_url)
    msme_login.login(
        username=login_data["username"],
        password=login_data["password"],
        otp=login_data["otp"],
    )

    internal_si_payment = InternalSiPaymentPage(page)
    internal_si_payment.internal_si_payment(internal_si_data)
