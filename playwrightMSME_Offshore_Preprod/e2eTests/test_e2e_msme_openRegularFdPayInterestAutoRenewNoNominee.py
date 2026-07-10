import json
from pathlib import Path

import pytest

from pageObjects.msmeLogin import MsmeLoginPage
from pageObjects.openRegularFdPayInterestAutoRenewNoNominee import (
    OpenRegularFdPayInterestAutoRenewNoNomineePage,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
LOGIN_DATA_PATH = PROJECT_ROOT / "TestData" / "msmeLogin.json"
OPEN_FD_DATA_PATH = (
    PROJECT_ROOT
    / "TestData"
    / "openRegularFdPayInterestAutoRenewNoNominee.json"
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


@pytest.mark.parametrize(
    "login_data",
    _load_json_data(LOGIN_DATA_PATH),
    ids=lambda data: data.get("case_id", data.get("username", "msme_login")),
)
@pytest.mark.parametrize(
    "open_fd_data",
    _load_json_data(OPEN_FD_DATA_PATH),
    ids=lambda data: data.get(
        "case_id",
        data.get("depositType", "open_regular_fd_no_nominee"),
    ),
)
def test_open_regular_fd_pay_interest_auto_renew_no_nominee(
    page,
    base_url,
    login_data,
    open_fd_data,
):
    msme_login = MsmeLoginPage(page, base_url)
    msme_login.login(
        username=login_data["username"],
        password=login_data["password"],
        otp=login_data["otp"],
    )

    open_fd = OpenRegularFdPayInterestAutoRenewNoNomineePage(page)
    open_fd.open_regular_fd_pay_interest_auto_renew_no_nominee(open_fd_data)
