# -*- coding: utf-8 -*-

import requests
import base64
import json
import logging
from datetime import datetime, timezone, time
from odoo.exceptions import ValidationError
from odoo import models, api, exceptions, fields


_logger = logging.getLogger(__name__)


class OmnaSyncProducts(models.TransientModel):
    _name = 'omna.sync_products_wizard'
    _inherit = 'omna.api'

    sync_type = fields.Selection([('all', 'All'),
                                  ('by_integration', 'By Integration'),
                                  ('by_external_id', 'By External Id'),
                                  ('import_updated_products', 'Import Updated Products from an Integration.'),
                                  ('number', 'Number')], 'Import Type',
                                 required=True, default='all')
    integration_id = fields.Many2one('omna.integration', 'Integration')
    template_id = fields.Many2one('product.template', 'Product')

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
        if self.sync_type not in ['number', 'by_external_id', 'import_updated_products']:
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
        elif self.sync_type == 'import_updated_products':
            self.import_resources()
        else:
            if self.sync_type == 'by_external_id':
                external = self.env['omna.template.integration.external.id'].search(
                    [('product_template_id', '=', self.template_id.id),
                     ('integration_id', '=', self.integration_id.integration_id)], limit=1)
                if external:
                    response = self.get(
                        'integrations/%s/products/%s' % (self.integration_id.integration_id, external.id_external),
                        {})
                else:
                    raise ValidationError(('Product %s was not found in integration %s') % (
                        self.template_id.name, self.integration_id.integration_id))
            else:
                omna_number = self.template_id.omna_product_id
                response = self.get(
                    'products/%s' % omna_number,
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
                if (len(product.get('images'))):
                    url = product.get('images')[0]
                    if url:
                        image = base64.b64encode(requests.get(url.strip()).content).replace(b'\n', b'')
                        data['image'] = image

                if self.sync_type in ['by_external_id', 'by_integration']:
                    if len(product.get('integration')):
                        integrations = []
                        list_category = []
                        list_brand = []
                        integration = product.get('integration')
                        integrations.append(product.get('integration').get('id'))
                        category_or_brands = integration.get('product').get('properties')
                        integration_id = self.env['omna.integration'].search(
                            [('integration_id', '=', integration.get('id'))])
                        if category_or_brands:
                            for cat_br in category_or_brands:
                                if (cat_br.get('label') == 'Category') and (cat_br.get('options')):
                                    category_id = cat_br.get('options')[0]['id']
                                    category_name = cat_br.get('options')[0]['name']
                                    arr = category_name.split('>')
                                    category_id = category_id
                                    category_obj = self.env['product.category']
                                    c_tree = self.category_tree(arr, False, category_id, integration_id.id,
                                                                category_obj, list_category)
                                    data['category_ids'] = [(6, 0, list_category)]

                                if (cat_br.get('label') == 'Brand'):
                                    brand_id = cat_br.get('id')
                                    brand_name = cat_br.get('value')
                                    brands = self.env['product.brand'].search(
                                        [('integration_id', '=', integration_id.id), '|',
                                         ('name', '=', brand_name),
                                         ('omna_brand_id', '=', brand_id)], limit=1)
                                    if brands:
                                        brands.write(
                                            {'name': brand_name, 'omna_brand_id': brand_id})
                                    else:
                                        brands = self.env['product.brand'].create(
                                            {'name': brand_name, 'omna_brand_id': brand_id,
                                             'integration_id': integration_id.id})
                                    list_brand.append(brands.id)
                        data['brand_ids'] = [(6, 0, list_brand)]

                        omna_integration = self.env['omna.integration'].search([('integration_id', 'in', integrations)])
                        for integration in omna_integration:
                            data['integration_ids'] = [(0, 0, {'integration_ids': [(4, integration.id, 0)]})]

                else:
                    if len(product.get('integrations')):
                        integrations = []
                        list_category = []
                        list_brand = []
                        for integration in product.get('integrations'):
                            integrations.append(integration.get('id'))
                            category_or_brands = integration.get('product').get('properties')
                            integration_id = self.env['omna.integration'].search(
                                [('integration_id', '=', integration.get('id'))])
                            for cat_br in category_or_brands:
                                if (cat_br.get('label') == 'Category') and (cat_br.get('options')):
                                    category_id = cat_br.get('options')[0]['id']
                                    category_name = cat_br.get('options')[0]['name']
                                    arr = category_name.split('>')
                                    category_id = category_id
                                    category_obj = self.env['product.category']
                                    c_tree = self.category_tree(arr, False, category_id, integration_id.id,
                                                                category_obj, list_category)
                                    data['category_ids'] = [(6, 0, list_category)]

                                if (cat_br.get('label') == 'Brand'):
                                    brand_id = cat_br.get('id')
                                    brand_name = cat_br.get('value')
                                    brands = self.env['product.brand'].search(
                                        [('integration_id', '=', integration_id.id), '|',
                                         ('name', '=', brand_name),
                                         ('omna_brand_id', '=', brand_id)], limit=1)
                                    if brands:
                                        brands.write(
                                            {'name': brand_name, 'omna_brand_id': brand_id})
                                    else:
                                        brands = self.env['product.brand'].create(
                                            {'name': brand_name, 'omna_brand_id': brand_id,
                                             'integration_id': integration_id.id})
                                    list_brand.append(brands.id)
                        data['brand_ids'] = [(6, 0, list_brand)]

                        omna_integration = self.env['omna.integration'].search([('integration_id', 'in', integrations)])
                        for integration in omna_integration:
                            # revisar aca porque me esta repitiendo la integracion, cuando no deberia ser
                            data['integration_ids'] = [(0, 0, {'integration_ids': [(4, integration.id, 0)]})]

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
                if len(product.get('images', [])):
                    url = product.get('images')[0]
                    if url:
                        image = base64.b64encode(requests.get(url.strip()).content).replace(b'\n', b'')
                        data['image'] = image

                if len(product.get('integrations')):
                    integrations = []
                    list_category = []
                    list_brand = []
                    data_external = []
                    for integration in product.get('integrations'):
                        integrations.append(integration.get('id'))
                        data['external_id_integration_ids'] = [(0, 0, {'integration_id': integration.get('id'),
                                                                       'id_external': integration.get('product').get(
                                                                           'remote_product_id')})]

                        category_or_brands = integration.get('product').get('properties')
                        integration_id = self.env['omna.integration'].search(
                            [('integration_id', '=', integration.get('id'))])
                        for cat_br in category_or_brands:
                            if (cat_br.get('label') == 'Category') and (cat_br.get('options')):
                                category_id = cat_br.get('options')[0]['id']
                                category_name = cat_br.get('options')[0]['name']

                                arr = category_name.split('>')
                                category_id = category_id
                                category_obj = self.env['product.category']
                                c_tree = self.category_tree(arr, False, category_id, integration_id.id,
                                                            category_obj, list_category)
                                data['category_ids'] = [(6, 0, list_category)]

                            if (cat_br.get('label') == 'Brand'):
                                brand_id = cat_br.get('id')
                                brand_name = cat_br.get('value')
                                brands = self.env['product.brand'].search(
                                    [('integration_id', '=', integration_id.id), '|',
                                     ('name', '=', brand_name),
                                     ('omna_brand_id', '=', brand_id)], limit=1)
                                if brands:
                                    brands.write(
                                        {'name': brand_name, 'omna_brand_id': brand_id})
                                else:
                                    brands = self.env['product.brand'].create(
                                        {'name': brand_name, 'omna_brand_id': brand_id,
                                         'integration_id': integration_id.id})
                                list_brand.append(brands.id)

                    data['brand_ids'] = [(6, 0, list_brand)]

                    omna_integration = self.env['omna.integration'].search([('integration_id', 'in', integrations)])
                    for integration in omna_integration:
                        data['integration_ids'] = [(0, 0, {'integration_ids': [(4, integration.id, 0)]})]
                    # data['external_id_integration_ids'] = [(6, 0, data_external)]

                act_product = product_obj.with_context(synchronizing=True).create(data)
                try:
                    # act_product = product_obj.with_context(synchronizing=True).create(data)
                    # if omna_integration:
                    #     integration = self.env['omna.integration_product'].create({
                    #         'product_template_id': act_product.id,
                    #         'integration_ids': [(6, 0, omna_integration.ids)]})
                    #     act_product.write({'integration_ids': [(6, 0, integration.ids)]})
                    self.import_variants(act_product.omna_product_id)
                except Exception as e:
                    _logger.error(e)

    def import_variants(self, product_id):
        limit = 100
        offset = 0
        flag = True
        products = []
        while flag:
            response = self.get('products/%s/variants' % product_id,
                                {'limit': limit, 'offset': offset, 'with_details': 'true'})
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
            act_product_template = product_template_obj.search(
                [('omna_product_id', '=', product.get('product').get('id'))])
            if act_product:
                data = {
                    'name': act_product_template.name,
                    'description': product.get('description'),
                    'lst_price': product.get('price'),
                    'default_code': product.get('sku'),
                    'standard_price': product.get('cost_price'),
                    'quantity': product.get('quantity'),
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
                    list_category = []
                    list_brand = []
                    for integration in product.get('integrations'):
                        integrations.append(integration.get('id'))
                        integration_id = self.env['omna.integration'].search(
                            [('integration_id', '=', integration.get('id'))])
                        category_or_brands = integration.get('variant').get('properties')

                        for cat_br in category_or_brands:
                            if (cat_br.get('label') == 'Category') and (cat_br.get('options')):
                                category_id = cat_br.get('options')[0]['id']
                                category_name = cat_br.get('options')[0]['name']

                                arr = category_name.split('>')
                                category_id = category_id
                                category_obj = self.env['product.category']
                                c_tree = self.category_tree(arr, False, category_id, integration_id.id,
                                                            category_obj, list_category)
                                data['category_ids'] = [(6, 0, list_category)]

                            if (cat_br.get('label') == 'Brand'):
                                brand_id = cat_br.get('id')
                                brand_name = cat_br.get('value')
                                brands = self.env['product.brand'].search(
                                    [('integration_id', '=', integration_id.id), '|',
                                     ('name', '=', brand_name),
                                     ('omna_brand_id', '=', brand_id)], limit=1)
                                if brands:
                                    brands.write(
                                        {'name': brand_name, 'omna_brand_id': brand_id})
                                else:
                                    brands = self.env['product.brand'].create(
                                        {'name': brand_name, 'omna_brand_id': brand_id,
                                         'integration_id': integration_id.id})
                                list_brand.append(brands.id)

                    data['brand_ids'] = [(6, 0, list_brand)]

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
                    'quantity': product.get('quantity'),
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
                    list_category = []
                    list_brand = []
                    data_external = []
                    for integration in product.get('integrations'):
                        integrations.append(integration.get('id'))
                        integration_id = self.env['omna.integration'].search(
                            [('integration_id', '=', integration.get('id'))])

                        category_or_brands = integration.get('variant').get('properties')
                        for cat_br in category_or_brands:
                            if (cat_br.get('label') == 'Category') and (cat_br.get('options')):
                                category_id = cat_br.get('options')[0]['id']
                                category_name = cat_br.get('options')[0]['name']

                                arr = category_name.split('>')
                                category_id = category_id
                                category_obj = self.env['product.category']
                                c_tree = self.category_tree(arr, False, category_id, integration_id.id,
                                                            category_obj, list_category)
                                data['category_ids'] = [(6, 0, list_category)]

                            if (cat_br.get('label') == 'Brand'):
                                brand_id = cat_br.get('id')
                                brand_name = cat_br.get('value')
                                brands = self.env['product.brand'].search(
                                    [('integration_id', '=', integration_id.id), '|',
                                     ('name', '=', brand_name),
                                     ('omna_brand_id', '=', brand_id)], limit=1)
                                if brands:
                                    brands.write(
                                        {'name': brand_name, 'omna_brand_id': brand_id})
                                else:
                                    brands = self.env['product.brand'].create(
                                        {'name': brand_name, 'omna_brand_id': brand_id,
                                         'integration_id': integration_id.id})
                                list_brand.append(brands.id)

                    data['brand_ids'] = [(6, 0, list_brand)]

                    data['external_id_integration_ids'] = [(0, 0, {'integration_id': integration.get('id'),
                                                                   'id_external': integration.get('variant').get(
                                                                       'remote_product_id')})]
                    # new_external = self.env['omna.template.integration.external.id'].create(
                    #     {'integration_id': integration.get('id'),
                    #      'external_id': integration.get('variant').get('remote_variant_id')})
                    # data_external.append(new_external.id)
                    ids = self.env['omna.integration'].search([('integration_id', 'in', integrations)]).ids
                    data['variant_integration_ids'] = [(6, 0, ids)]
                    # data['external_id_integration_ids'] = [(6, 0, data_external)]

                act_product = product_obj.with_context(synchronizing=True).create(data)
                if act_product:
                    return True

    def import_resources(self):
        try:
            result = self.get('integrations/%s/products/import' % self.integration_id.integration_id, {})

            self.env.user.notify_channel('warning', (
                'The task to import the resources have been created, please go to "System\Tasks" to check out the task status.'),
                                         ("Information"), True)
            return {'type': 'ir.actions.act_window_close'}

        except Exception as e:
            _logger.error(e)
            raise exceptions.AccessError(e)

    def category_tree(self, arr, parent_id, category_id, integration_id, category_obj, list_category):
        # integration_id = self.env['omna.integration'].search([('name', '=', integration_category_name)])
        if len(arr) == 1:
            name = arr[0]
            c = category_obj.search(['|', ('omna_category_id', '=', category_id), '&',
                                     ('name', '=', name), ('parent_id', '=', parent_id),
                                     ('integration_id', '=', integration_id)], limit=1)
            if not c:
                c = category_obj.create({'name': name, 'omna_category_id': category_id,
                                         'parent_id': parent_id,
                                         'integration_id': integration_id})

            else:
                c.write({'name': name, 'parent_id': parent_id})

            list_category.append(c.id)
            return list_category

        elif len(arr) > 1:
            name = arr[0]
            c = category_obj.search(
                [('name', '=', name), ('integration_category_name', '=', integration_id)], limit=1)
            if not c:
                c = category_obj.create(
                    {'name': name, 'parent_id': parent_id, 'integration_category_name': integration_id})

            list_category.append(c.id)
            self.category_tree(arr[1:], c.id if c else False, category_id, integration_id, category_obj,
                               list_category)
