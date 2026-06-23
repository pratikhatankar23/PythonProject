import json
from pathlib import Path

import pytest

from pageObjects.msmeLogin import MsmeLoginPage
from pageObjects.paySalaryRtgs import PaySalaryRtgsPage


PROJECT_ROOT = Path(__file__).resolve().parents[1]
LOGIN_DATA_PATH = PROJECT_ROOT / "TestData" / "msmeLogin.json"
PAY_SALARY_RTGS_DATA_PATH = PROJECT_ROOT / "TestData" / "paySalaryRtgs.json"


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
    "salary_data",
    _load_json_data(PAY_SALARY_RTGS_DATA_PATH),
    ids=lambda data: data.get(
        "case_id",
        data.get("employeeName", "pay_salary_rtgs"),
    ),
)
def test_pay_salary_rtgs(page, base_url, login_data, salary_data):
    msme_login = MsmeLoginPage(page, base_url)
    msme_login.login(
        username=login_data["username"],
        password=login_data["password"],
        otp=login_data["otp"],
    )

    salary_payment = PaySalaryRtgsPage(page)
    salary_payment.pay_salary_rtgs(salary_data)
