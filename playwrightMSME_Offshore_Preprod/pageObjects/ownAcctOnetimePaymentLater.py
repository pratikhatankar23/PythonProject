from pageObjects.ownAcctOnetimePayment import OwnAcctOnetimePaymentPage


class OwnAcctOnetimePaymentLaterPage(OwnAcctOnetimePaymentPage):
    REQUIRE_TRANSFER_TIME_FOR_DATED_TRANSFER = True
    ALLOW_MISSING_TRANSFER_TIME_FIELD = True
