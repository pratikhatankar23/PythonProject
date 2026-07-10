from pageObjects.internalRegPayeeOnetimePayment import (
    InternalRegPayeeOnetimePaymentPage,
)


class InternalRegPayeeOnetimePaymentLaterPage(InternalRegPayeeOnetimePaymentPage):
    REQUIRE_TRANSFER_TIME_FOR_DATED_TRANSFER = True
