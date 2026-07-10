import json
from pathlib import Path

import pytest

from pageObjects.msmeLogin import MsmeLoginPage
from pageObjects.ownAcctSiPaymentSelectEndDate import (
    OwnAcctSiPaymentSelectEndDatePage,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
LOGIN_DATA_PATH = PROJECT_ROOT / "TestData" / "msmeLogin.json"
OWN_ACCOUNT_SI_SELECT_END_DATE_DATA_PATH = (
    PROJECT_ROOT / "TestData" / "ownAcctSiPaymentSelectEndDate.json"
)


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

@pytest.mark.smoke
@pytest.mark.parametrize(
    "login_data",
    _load_json_data(LOGIN_DATA_PATH),
    ids=lambda data: data.get("case_id", data.get("username", "msme_login")),
)
@pytest.mark.parametrize(
    "own_account_si_select_end_date_data",
    _load_json_data(OWN_ACCOUNT_SI_SELECT_END_DATE_DATA_PATH),
    ids=lambda data: data.get(
        "case_id",
        f"{data.get('from_account', 'from')}_to_{data.get('to_account', 'to')}_si_end_date",
    ),
)
def test_own_account_si_payment_select_end_date(
    page,
    base_url,
    login_data,
    own_account_si_select_end_date_data,
):
    msme_login = MsmeLoginPage(page, base_url)
    msme_login.login(
        username=login_data["username"],
        password=login_data["password"],
        otp=login_data["otp"],
    )

    own_account_si_payment = OwnAcctSiPaymentSelectEndDatePage(page)
    own_account_si_payment.own_account_si_payment_select_end_date(
        own_account_si_select_end_date_data
    )
