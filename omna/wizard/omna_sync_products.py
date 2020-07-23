# -*- coding: utf-8 -*-

import requests
import base64
import json
import logging
from datetime import datetime, timezone, time
from odoo import models, api, exceptions, fields


_logger = logging.getLogger(__name__)


class OmnaSyncProducts(models.TransientModel):
    _name = 'omna.sync_products_wizard'
    _inherit = 'omna.api'

    sync_type = fields.Selection([('all', 'All'),
                                  ('by_integration', 'By Integration'),
                                  ('by_external_id', 'By External Id'),
                                  ('number', 'Number')], 'Import Type',
                                 required=True, default='all')
    integration_id = fields.Many2one('omna.integration', 'Integration')
    number = fields.Char(u"Omna's Product Number")
    external_id = fields.Char(u"External Product Id")

    @api.onchange('sync_type')
    def onchange_sync_type(self):
        if self.sync_type == 'by_external_id':
            self.number = False
        elif self.sync_type == 'number':
            self.external_id = False

    def sync_products(self):
        try:
            self.import_products()
            return {
                'type': 'ir.actions.client',
                'tag': 'reload'
            }
        except Exception as e:
            _logger.error(e)
            raise exceptions.AccessError(e)
        pass

    def import_products(self):
        limit = 100
        offset = 0
        flag = True
        products = []
        if self.sync_type not in ['number', 'by_external_id']:
            while flag:
                if self.sync_type == 'all':
                    response = self.get('products', {'limit': limit, 'offset': offset, 'with_details': 'true'})
                else:
                    response = self.get(
                        'integrations/%s/products' % self.integration_id.integration_id,
                        {'limit': limit, 'offset': offset})
                data = response.get('data')
                products.extend(data)
                if len(data) < limit:
                    flag = False
                else:
                    offset += limit
        else:
            if self.sync_type == 'by_external_id':
                response = self.get(
                    'integrations/%s/products/%s' % (self.integration_id.integration_id, self.external_id),
                    {})
            else:
                response = self.get(
                    'products/%s' % self.number,
                    {})
            data = response.get('data')
            products.append(data)

        product_obj = self.env['product.template']
        for product in products:
            act_product = product_obj.search([('omna_product_id', '=', product.get('id'))])
            if act_product:
                data = {
                    'name': product.get('name'),
                    'description': product.get('description'),
                    'list_price': product.get('price'),
                    'integrations_data': json.dumps(product.get('integrations'), separators=(',', ':'))
                }
                if len(product.get('images')):
                    url = product.get('images')[0]
                    if url:
                        image = base64.b64encode(requests.get(url.strip()).content).replace(b'\n', b'')
                        data['image'] = image

                if len(product.get('integrations')):
                    integrations = []
                    for integration in product.get('integrations'):
                        integrations.append(integration.get('id'))
                    # ids = self.env['omna.integration'].search([('integration_id', 'in', integrations)]).ids
                    # data['integration_ids'] = [(6, 0, ids)]
                    omna_integration = self.env['omna.integration'].search([('integration_id', 'in', integrations)])
                    data['integration_ids'] = [(0, 0, {'integration_ids': [(6, 0, omna_integration.ids)]})]

                act_product.with_context(synchronizing=True).write(data)
                try:
                    self.import_variants(act_product.omna_product_id)
                except Exception as e:
                    _logger.error(e)
            else:
                data = {
                    'name': product.get('name'),
                    'omna_product_id': product.get('id'),
                    'description': product.get('description'),
                    'list_price': product.get('price'),
                    'integrations_data': json.dumps(product.get('integrations'), separators=(',', ':'))
                }
                if len(product.get('images')):
                    url = product.get('images')[0]
                    if url:
                        image = base64.b64encode(requests.get(url.strip()).content).replace(b'\n', b'')
                        data['image'] = image

                if len(product.get('integrations')):
                    integrations = []
                    for integration in product.get('integrations'):
                        integrations.append(integration.get('id'))
                    # ids = self.env['omna.integration'].search([('integration_id', 'in', integrations)]).ids
                    # data['integration_ids'] = [(6, 0, ids)]
                    omna_integration = self.env['omna.integration'].search([('integration_id', 'in', integrations)])
                    data['integration_ids'] = [(0, 0, {'integration_ids': [(6, 0, omna_integration.ids)]})]

                act_product = product_obj.with_context(synchronizing=True).create(data)
                try:
                    self.import_variants(act_product.omna_product_id)
                except Exception as e:
                    _logger.error(e)

    def import_variants(self, product_id):
        limit = 100
        offset = 0
        flag = True
        products = []
        while flag:
            response = self.get('products/%s/variants' % product_id, {'limit': limit, 'offset': offset, 'with_details': 'true'})
            data = response.get('data')
            products.extend(data)
            if len(data) < limit:
                flag = False
            else:
                offset += limit

        product_obj = self.env['product.product']
        product_template_obj = self.env['product.template']
        for product in products:
            act_product = product_obj.search([('omna_variant_id', '=', product.get('id'))])
            act_product_template = product_template_obj.search([('omna_product_id', '=', product.get('product').get('id'))])
            if act_product:
                data = {
                    'name': act_product_template.name,
                    'description': product.get('description'),
                    'lst_price': product.get('price'),
                    'default_code': product.get('sku'),
                    'standard_price': product.get('cost_price'),
                    'product_tmpl_id': act_product_template.id,
                    'variant_integrations_data': json.dumps(product.get('integrations'), separators=(',', ':'))
                }
                if len(product.get('images')):
                    url = product.get('images')[0]
                    if url:
                        image = base64.b64encode(requests.get(url.strip()).content).replace(b'\n', b'')
                        data['image_variant'] = image

                if len(product.get('integrations')):
                    integrations = []
                    for integration in product.get('integrations'):
                        integrations.append(integration.get('id'))
                    ids = self.env['omna.integration'].search([('integration_id', 'in', integrations)]).ids
                    data['variant_integration_ids'] = [(6, 0, ids)]

                act_product.with_context(synchronizing=True).write(data)
            else:
                data = {
                    'name': act_product_template.name,
                    'description': product.get('description'),
                    'lst_price': product.get('price'),
                    'default_code': product.get('sku'),
                    'standard_price': product.get('cost_price'),
                    'omna_variant_id': product.get('id'),
                    'product_tmpl_id': act_product_template.id,
                    'variant_integrations_data': json.dumps(product.get('integrations'), separators=(',', ':'))
                }
                if len(product.get('images')):
                    url = product.get('images')[0]
                    if url:
                        image = base64.b64encode(requests.get(url.strip()).content).replace(b'\n', b'')
                        data['image_variant'] = image

                if len(product.get('integrations')):
                    integrations = []
                    for integration in product.get('integrations'):
                        integrations.append(integration.get('id'))
                    ids = self.env['omna.integration'].search([('integration_id', 'in', integrations)]).ids
                    data['variant_integration_ids'] = [(6, 0, ids)]

                act_product = product_obj.with_context(synchronizing=True).create(data)
