# -*- coding: utf-8 -*-

import logging, odoo
from datetime import datetime, timezone
import dateutil.parser
from odoo import models, api, exceptions, fields, _
import pytz

_logger = logging.getLogger(__name__)


class LinkVariantWizard(models.TransientModel):
    _name = 'link.variant.wizard'
    _inherit = 'omna.api'



    omna_integration_id = fields.Many2one('omna.integration', 'Integration to Link', required=True)



    def action_link_variant(self):
        # Agregar validacion para que no se intente linkear con una integracion que ya tenga linkeada.
        try:
            product_template_obj = self.env['product.template']
            product_product_obj = self.env['product.product']
            integrations = [self.omna_integration_id.integration_id]
            data = {
                'data': {
                    'integration_ids': integrations,
                }
            }
            # https: // cenit.io / app / ecapi - v1 / products / {product_id} / variants / {variant_id}
            product = product_template_obj.search([('id', '=', self.env.context.get('default_product_template_id'))])
            variant = product_product_obj.search([('id', '=', self.env.context.get('active_id'))])
            route = 'products/%s/variants/%s' % (product.omna_product_id, variant.omna_variant_id)
            response = self.put(route, data)
            variant.write({'variant_integration_ids': [(4, self.omna_integration_id.id)]})
            self.env.cr.commit()
            return True
        except Exception:
            raise exceptions.AccessError(_("Error trying to update variant products in Omna's API."))
        return {'type': 'ir.actions.act_window_close'}



    def action_unlink_variant(self):
        # Agregar validacion para que no se intente deslinkear con una integracion que ya tenga deslinkeada.
        try:
            product_template_obj = self.env['product.template']
            product_product_obj = self.env['product.product']
            integrations = [self.omna_integration_id.integration_id]
            data = {
                'data': {
                    'integration_ids': integrations,
                    'delete_from_integration': True
                }
            }
            # https: // cenit.io / app / ecapi - v1 / products / {product_id} / variants / {variant_id}
            product = product_template_obj.search([('id', '=', self.env.context.get('default_product_template_id'))])
            variant = product_product_obj.search([('id', '=', self.env.context.get('active_id'))])
            route = 'products/%s/variants/%s' % (product.omna_product_id, variant.omna_variant_id)
            response = self.patch(route, data)
            variant.write({'variant_integration_ids': [(3, self.omna_integration_id.id)]})
            self.env.cr.commit()
            return True
        except Exception:
            raise exceptions.AccessError(_("Error trying to update variant products in Omna's API."))
        return {'type': 'ir.actions.act_window_close'}
