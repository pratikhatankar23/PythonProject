import json
from pathlib import Path

import pytest

from pageObjects.addDomesticBeneSalary import AddDomesticBeneSalaryPage
from pageObjects.msmeLogin import MsmeLoginPage


PROJECT_ROOT = Path(__file__).resolve().parents[1]
LOGIN_DATA_PATH = PROJECT_ROOT / "TestData" / "msmeLogin.json"
SALARY_DATA_PATH = PROJECT_ROOT / "TestData" / "addDomesticBeneSalary.json"


def _load_json_data(path):
    with path.open(encoding="utf-8") as data_file:
        data = json.load(data_file)

    if not isinstance(data, list):
        raise ValueError(f"{path.name} must contain a list of data dictionaries.")

    return data


@pytest.mark.parametrize(
    "login_data",
    _load_json_data(LOGIN_DATA_PATH),
    ids=lambda data: data.get("case_id", data.get("username", "msme_login")),
)
@pytest.mark.parametrize(
    "salary_data",
    _load_json_data(SALARY_DATA_PATH),
    ids=lambda data: data.get("case_id", data.get("empNickName", "domestic_salary")),
)
def test_add_domestic_bene_salary(page, base_url, login_data, salary_data):
    msme_login = MsmeLoginPage(page, base_url)
    msme_login.login(
        username=login_data["username"],
        password=login_data["password"],
        otp=login_data["otp"],
    )

    add_salary_bene = AddDomesticBeneSalaryPage(page)
    add_salary_bene.add_domestic_bene_salary(salary_data)
