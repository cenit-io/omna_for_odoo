# -*- coding: utf-8 -*-

import requests
import base64
import json
import logging
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
            response = self.get('products', {'limit': limit, 'offset': offset, 'with_details': 'true'})
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
                    'list_price': product.get('price'),
                    'integrations_data': json.dumps(product.get('integrations'), separators=(',', ':'))
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
                    ids = self.env['omna.integration'].search([('integration_id', 'in', integrations)]).ids
                    data['integration_ids'] = [(6, 0, ids)]

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
                        data['image_1920'] = image

                if len(product.get('integrations')):
                    integrations = []
                    for integration in product.get('integrations'):
                        integrations.append(integration.get('id'))
                    ids = self.env['omna.integration'].search([('integration_id', 'in', integrations)]).ids
                    data['integration_ids'] = [(6, 0, ids)]

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
            if len(product.get('integrations')):
                act_product = product_obj.search([('omna_variant_id', '=', product.get('id'))])
                act_product_template = product_template_obj.search([('omna_product_id', '=', product.get('product').get('id'))])
                if act_product:
                    attrs = self.create_attributes(act_product_template.id, product.get('integrations'))
                    data = {
                        'name': act_product_template.name,
                        'description': product.get('description'),
                        'lst_price': product.get('price'),
                        'default_code': product.get('sku'),
                        'standard_price': product.get('cost_price'),
                        'product_tmpl_id': act_product_template.id,
                        'variant_integrations_data': json.dumps(product.get('integrations'), separators=(',', ':')),
                        'product_template_attribute_value_ids': attrs
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
                        ids = self.env['omna.integration'].search([('integration_id', 'in', integrations)]).ids
                        data['variant_integration_ids'] = [(6, 0, ids)]

                    act_product.with_context(synchronizing=True).write(data)
                else:
                    attrs = self.create_attributes(act_product_template.id, product.get('integrations'))
                    data = {
                        'name': act_product_template.name,
                        'description': product.get('description'),
                        'lst_price': product.get('price'),
                        'default_code': product.get('sku'),
                        'standard_price': product.get('cost_price'),
                        'omna_variant_id': product.get('id'),
                        'product_tmpl_id': act_product_template.id,
                        'variant_integrations_data': json.dumps(product.get('integrations'), separators=(',', ':')),
                        'product_template_attribute_value_ids': attrs
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
                        ids = self.env['omna.integration'].search([('integration_id', 'in', integrations)]).ids
                        data['variant_integration_ids'] = [(6, 0, ids)]

                    act_product = product_obj.with_context(synchronizing=True).create(data)

    def create_attributes(self, product_tmpl_id, integration_data):
        attr_value_obj = self.env['product.attribute.value']
        attr_obj = self.env['product.attribute']
        attr_line_obj = self.env['product.template.attribute.line']
        attr_temp_value_obj = self.env['product.template.attribute.value']
        attrs = [(5, 0, 0)]
        for integration in integration_data:
            if 'variant' in integration and 'properties' in integration['variant']:
                for attribute in integration['variant']['properties']:
                    attribute_name = attribute['name'] if 'name' in attribute else attribute['id']
                    name = integration['id'] + '-' + str(attribute_name)
                    attribute_value = self.format_value(attribute)
                    act_attr_line = attr_line_obj.search(
                            [('product_tmpl_id', '=', product_tmpl_id), ('attribute_id.name', '=', name), ('value_ids.name', '=', attribute_value)])

                    if act_attr_line:
                        act_temp_value = attr_temp_value_obj.search([('attribute_line_id', '=', act_attr_line.id), ('product_attribute_value_id.name', '=', attribute_value)], limit=1)
                        attrs.append((4, act_temp_value.id, 0))
                    else:
                        values = self.format_posible_values(attribute,attribute_value)
                        attr = attr_obj.create({
                            'name': name,
                            'value_ids': values,
                            'create_variant': 'no_variant'
                        })
                        values = []
                        current_value = False
                        for value in attr.value_ids:
                            values.append((4, value.id, 0))
                        line = attr_line_obj.create({
                            'product_tmpl_id': product_tmpl_id,
                            'attribute_id': attr.id,
                            'value_ids': values
                        })
                        for temp_value in line.product_template_value_ids:
                            if temp_value.name == attribute_value:
                                current_value = temp_value.id

                        attrs.append((4, current_value, 0))

        return attrs

    def format_value(self, attribute):
        if attribute['input_type'] == 'numeric':
            return str(attribute['value'])
        else:
            return str(attribute['value']) if attribute['value'] else 'None'

    def format_posible_values(self, attribute, attribute_value):
        values = []
        if attribute['input_type'] == 'single_select' or attribute['input_type'] == 'category_select_box' or attribute[
            'input_type'] == 'enum_input':
            have_none = False
            for option in attribute['options']:
                values.append((0, 0, {'name': str(option)}))
            if attribute_value == 'None' and not have_none:
                values.append((0, 0, {'name': 'None'}))
        else:
            values.append((0, 0, {'name': attribute_value}))

        return values




