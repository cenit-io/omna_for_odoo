# -*- coding: utf-8 -*-

import logging
from odoo import models, api, exceptions


_logger = logging.getLogger(__name__)


class OmnaSyncOrders(models.TransientModel):
    _name = 'omna.sync_orders_wizard'
    _inherit = 'omna.api'

    def sync_orders(self):
        try:
            limit = 100
            offset = 0
            requester = True
            orders = []
            while requester:
                response = self.get('orders', {'limit': limit, 'offset': offset})
                data = response.get('data')
                orders.extend(data)
                if len(data) < limit:
                    requester = False
                else:
                    offset += limit

            self.env['omna.order.mixin'].sync_orders(orders)

            return {
                'type': 'ir.actions.client',
                'tag': 'reload'
            }

        except Exception as e:
            _logger.error(e)
            raise exceptions.AccessError(e)

