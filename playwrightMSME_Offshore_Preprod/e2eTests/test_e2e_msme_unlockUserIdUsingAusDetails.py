import json
from pathlib import Path

import pytest

from pageObjects.unlockUserIdUsingAusDetails import UnlockUserIdUsingAusDetailsPage


PROJECT_ROOT = Path(__file__).resolve().parents[1]
UNLOCK_USER_ID_DATA_PATH = (
    PROJECT_ROOT / "TestData" / "unlockUserIdUsingAusDetails.json"
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
    "unlock_user_id_data",
    _load_json_data(UNLOCK_USER_ID_DATA_PATH),
    ids=lambda data: data.get(
        "case_id",
        data.get("userId", "unlock_user_id_using_aus_details"),
    ),
)
def test_unlock_user_id_using_aus_details(
    page,
    base_url,
    unlock_user_id_data,
):
    unlock_user_id = UnlockUserIdUsingAusDetailsPage(page, base_url)
    unlock_user_id.unlock_user_id_using_aus_details(unlock_user_id_data)
