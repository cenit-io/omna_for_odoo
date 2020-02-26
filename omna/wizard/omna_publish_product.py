# -*- coding: utf-8 -*-

import logging, odoo
from datetime import datetime, timezone
import dateutil.parser
from odoo import models, api, exceptions, fields
import pytz

_logger = logging.getLogger(__name__)


class OmnaPublishProductWizard(models.TransientModel):
    _name = 'omna.publish_product_wzd'
    _inherit = 'omna.api'

    product_id = fields.Many2one('product.template', 'Product', required=True)
    integration_ids = fields.Many2many('omna.integration', 'omna_publish_product_wzd_integration_rel', 'publish_product_id', 'integration_id', 'Integrations', required=True)

    def publish_product(self):
        try:
            integrations = []
            for integration in self.integration_ids:
                integrations.append(integration.integration_id)
            data = {
                'data': {
                    'integration_ids': integrations
                }
            }
            self.put('products/%s' % self.product_id.omna_product_id, data)
            return True
        except Exception as e:
            _logger.error(e)
            raise exceptions.AccessError(e)
