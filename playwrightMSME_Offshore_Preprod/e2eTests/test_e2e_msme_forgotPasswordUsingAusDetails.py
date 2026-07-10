import json
from pathlib import Path

import pytest

from pageObjects.forgotPasswordUsingAusDetails import (
    ForgotPasswordUsingAusDetailsPage,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
FORGOT_PASSWORD_DATA_PATH = (
    PROJECT_ROOT / "TestData" / "forgotPasswordUsingAusDetails.json"
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

@pytest.mark.smokePreProd
@pytest.mark.parametrize(
    "forgot_password_data",
    _load_json_data(FORGOT_PASSWORD_DATA_PATH),
    ids=lambda data: data.get(
        "case_id",
        data.get("userId", "forgot_password_using_aus_details"),
    ),
)
def test_forgot_password_using_aus_details(
    page,
    base_url,
    forgot_password_data,
):
    forgot_password = ForgotPasswordUsingAusDetailsPage(page, base_url)
    forgot_password.forgot_password_using_aus_details(forgot_password_data)
