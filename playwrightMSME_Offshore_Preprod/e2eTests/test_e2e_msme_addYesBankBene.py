import json
from pathlib import Path

import pytest

from pageObjects.addYesBankBene import AddYesBankBenePage
from pageObjects.msmeLogin import MsmeLoginPage


PROJECT_ROOT = Path(__file__).resolve().parents[1]
LOGIN_DATA_PATH = PROJECT_ROOT / "TestData" / "msmeLogin.json"
BENE_DATA_PATH = PROJECT_ROOT / "TestData" / "addYesBankBene.json"


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
    "bene_data",
    _load_json_data(BENE_DATA_PATH),
    ids=lambda data: data.get("case_id", data.get("beneNickName", "yes_bank_bene")),
)
def test_add_yes_bank_beneficiary(page, base_url, login_data, bene_data):
    msme_login = MsmeLoginPage(page, base_url)
    msme_login.login(
        username=login_data["username"],
        password=login_data["password"],
        otp=login_data["otp"],
    )

    add_bene = AddYesBankBenePage(page)
    add_bene.add_yes_bank_beneficiary(bene_data)
