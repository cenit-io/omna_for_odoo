# -*- coding: utf-8 -*-

import requests
import base64
import json
import logging
import hmac
import hashlib
from datetime import datetime, timezone, time
from odoo import models, api, exceptions


_logger = logging.getLogger(__name__)


class OmnaSyncProducts(models.TransientModel):
    _name = 'omna.sync_products_wizard'
    _inherit = 'omna.api'

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
        while flag:
            response = self.get('products', {'limit': limit, 'offset': offset})
            data = response.get('data')
            products.extend(data)
            if len(data) < limit:
                flag = False
            else:
                offset += limit

        product_obj = self.env['product.template']
        for product in products:
            act_product = product_obj.search([('omna_product_id', '=', product.get('id'))])
            if act_product:
                data = {
                    'name': product.get('name'),
                    'description': product.get('description'),
                    'list_price': product.get('price')
                }
                if len(product.get('images')):
                    url = product.get('images')[0]
                    if url:
                        image = base64.b64encode(requests.get(url.strip()).content).replace(b'\n', b'')
                        data['image_1920'] = image

                if len(product.get('integrations')):
                    integrations = []
                    for integration in product.get('integrations'):
                        integrations.append(integration.get('id'))
                    data['integration_ids'] = self.env['omna.integration'].search([('integration_id', 'in', integrations)])

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
                    'list_price': product.get('price')
                }
                if len(product.get('images')):
                    url = product.get('images')[0]
                    if url:
                        image = base64.b64encode(requests.get(url.strip()).content).replace(b'\n', b'')
                        data['image_1920'] = image

                if len(product.get('integrations')):
                    integrations = []
                    for integration in product.get('integrations'):
                        integrations.append(integration.get('id'))
                    data['integration_ids'] = self.env['omna.integration'].search([('integration_id', 'in', integrations)])

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
            response = self.get('products/%s/variants' % product_id, {'limit': limit, 'offset': offset})
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
                    'product_tmpl_id': act_product_template.id
                }
                if len(product.get('images')):
                    url = product.get('images')[0]
                    if url:
                        image = base64.b64encode(requests.get(url.strip()).content).replace(b'\n', b'')
                        data['image_variant_1920'] = image

                if len(product.get('integrations')):
                    integrations = []
                    for integration in product.get('integrations'):
                        integrations.append(integration.get('id'))
                    data['variant_integration_ids'] = self.env['omna.integration'].search([('integration_id', 'in', integrations)])

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
                }
                if len(product.get('images')):
                    url = product.get('images')[0]
                    if url:
                        image = base64.b64encode(requests.get(url.strip()).content).replace(b'\n', b'')
                        data['image_variant_1920'] = image

                if len(product.get('integrations')):
                    integrations = []
                    for integration in product.get('integrations'):
                        integrations.append(integration.get('id'))
                    data['variant_integration_ids'] = self.env['omna.integration'].search([('integration_id', 'in', integrations)])

                act_product = product_obj.with_context(synchronizing=True).create(data)
