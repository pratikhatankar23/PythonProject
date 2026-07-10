from pageObjects.neftRegPayeeOnetime import NeftRegPayeeOnetimePage


class NeftRegPayeeOnetimeLaterPage(NeftRegPayeeOnetimePage):
    REQUIRE_TRANSFER_TIME_FOR_DATED_TRANSFER = True
