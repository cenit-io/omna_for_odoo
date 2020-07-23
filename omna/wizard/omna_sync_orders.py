# -*- coding: utf-8 -*-

import logging
from odoo import models, fields, api, exceptions

_logger = logging.getLogger(__name__)


class OmnaSyncOrders(models.TransientModel):
    _name = 'omna.sync_orders_wizard'
    _inherit = 'omna.api'

    sync_type = fields.Selection([('all', 'All'),
                                  ('by_integration',
                                   'By Integration'),
                                  ('number', 'Number')], 'Import Type',
                                 required=True, default='all')
    integration_id = fields.Many2one('omna.integration', 'Integration')
    number = fields.Char("Order Number")

    def sync_orders(self):
        try:
            limit = 100
            offset = 0
            requester = True
            orders = []
            if self.sync_type != 'number':
                while requester:
                    if self.sync_type == 'all':
                        response = self.get('orders',
                                            {'limit': limit, 'offset': offset})
                    else:
                        # path = integrations/{integration_id}/orders
                        response = self.get(
                            'integrations/%s/orders' % self.integration_id.integration_id,
                            {'limit': limit, 'offset': offset})
                    data = response.get('data')
                    orders.extend(data)
                    if len(data) < limit:
                        requester = False
                    else:
                        offset += limit
            else:
                # path = integrations/{integration_id}/orders/{number}
                response = self.get(
                    'integrations/%s/orders/%s' % (
                        self.integration_id.integration_id, self.number),
                    {})
                data = response.get('data')
                orders.append(data)

            self.env['omna.order.mixin'].sync_orders(orders)

            return {
                'type': 'ir.actions.client',
                'tag': 'reload'
            }

        except Exception as e:
            _logger.error(e)
            raise exceptions.AccessError(e)

