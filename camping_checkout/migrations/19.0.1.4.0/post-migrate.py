import logging

_logger = logging.getLogger(__name__)

_CAMPING_WEBSITE_DOMAIN = "https://camping.unternhub.at"


def migrate(cr, version):
    """Move the Address checkout step after Order, right before Payment."""
    cr.execute(
        """
        UPDATE website_checkout_step AS address
        SET sequence = order_step.sequence + 10
        FROM website AS website,
             website_checkout_step AS order_step
        WHERE address.website_id = website.id
          AND website.domain = %s
          AND address.step_href = '/shop/checkout'
          AND order_step.website_id = website.id
          AND order_step.step_href = '/shop/cart'
        """,
        (_CAMPING_WEBSITE_DOMAIN,),
    )
    _logger.info("camping_checkout: moved Address checkout step after Order")
