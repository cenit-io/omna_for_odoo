# -*- coding: utf-8 -*-

import requests
import base64
import json
import logging
from datetime import datetime, timezone, time
from odoo.exceptions import ValidationError
from odoo import models, api, exceptions, fields

_logger = logging.getLogger(__name__)


class OmnaSyncVariant(models.TransientModel):
    _name = 'omna.sync_variant_wizard'
    _inherit = 'omna.api'

    sync_type = fields.Selection([('all', 'All of the Product'),
                                  ('by_external_id', 'By External ID')], 'Import Type',
                                 required=True, default='all')
    integration_id = fields.Many2one('omna.integration', 'Integration', required=True)
    template_id = fields.Many2one('product.template', 'Product', required=True)
    variant_id = fields.Many2one('product.product', 'Product Variant', domain="[('product_tmpl_id', '=', template_id)]")

    # external_variant_id = fields.Char(u"External Product Variant Id")

    def sync_variants(self):
        try:
            self.import_variants()
            return {
                'type': 'ir.actions.client',
                'tag': 'reload'
            }
        except Exception as e:
            _logger.error(e)
            raise exceptions.AccessError(e)
        pass

    def import_variants(self):
        limit = 100
        offset = 0
        flag = True
        products = []
        # while flag:
        #     response = self.get('products/%s/variants' % product_id, {'limit': limit, 'offset': offset, 'with_details': 'true'})
        #     data = response.get('data')
        #     products.extend(data)
        #     if len(data) < limit:
        #         flag = False
        #     else:
        #         offset += limit
        template_ext_id = self.env['omna.template.integration.external.id'].search(
            [('integration_id', '=', self.integration_id.integration_id),
             ('product_template_id', '=', self.template_id.id)],
            limit=1)
        ext_id = template_ext_id.id_external
        if template_ext_id:
            if self.sync_type != 'by_external_id':
                while flag:
                    if self.sync_type == 'all':
                        response = self.get(
                            'integrations/%s/products/%s/variants' % (self.integration_id.integration_id,
                                                                      ext_id), {'limit': limit, 'offset': offset})

                    data = response.get('data')
                    products.extend(data)
                    if len(data) < limit:
                        flag = False
                    else:
                        offset += limit
            else:
                if self.sync_type == 'by_external_id':
                    extermal = self.env['omna.template.integration.external.id'].search(
                        [('product_template_id', '=', self.variant_id.id),
                         ('integration_id', '=', self.integration_id.integration_id)], limit=1)
                    # extermal_template = self.env['omna.template.integration.external.id'].search(
                    #     [('product_template_id', '=', self.template_id.id),
                    #     ('integration_id', '=', self.integration_id.id)], limit=1)
                    if extermal and ext_id:
                        response = self.get(
                            'integrations/%s/products/%s/variants/%s' % (
                            self.integration_id.integration_id, ext_id, extermal.id_external,
                            ),
                            {})
                    else:
                        raise ValidationError(
                            ('The product %s, with the variant %s, was not found in integration %s') % (
                                self.template_id.name, self.variant_id.display_name,
                                self.integration_id.integration_id))

                # else:
                #     response = self.get(
                #         'products/%s' % self.number,
                #         {})
                data = response.get('data')
                products.append(data)

        product_obj = self.env['product.product']
        product_template_obj = self.env['product.template']
        for product in products:
            act_product = product_obj.search([('omna_variant_id', '=', product.get('id'))])
            act_product_template = product_template_obj.search(
                [('omna_product_id', '=', product.get('product').get('id'))])
            if act_product_template:
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

                    if len(product.get('integration')):
                        integrations = []
                        data_external = []
                        list_category = []
                        list_brand = []
                        integration = product.get('integration')
                        integrations.append(product.get('integration').get('id'))

                        data['external_id_integration_ids'] = [(0, 0, {'integration_id': integration.get('id'),
                                                                       'id_external': integration.get(
                                                                           'variant').get('remote_product_id')})]
                        category_or_brands = integration.get('variant').get('properties')
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

                        ids = self.env['omna.integration'].search([('integration_id', 'in', integrations)]).ids
                        data['variant_integration_ids'] = [(6, 0, ids)]
                        # data['external_id_integration_ids'] = [(6, 0, data_external)]

                    act_product.with_context(synchronizing=True).write(data)
                else:
                    data = {
                        'name': act_product_template.name,
                        'description': product.get('description'),
                        'lst_price': product.get('price'),
                        'default_code': product.get('sku'),
                        'standard_price': product.get('cost_price'),
                        'quantity': product.get('quantity'),
                        'omna_variant_id': product.get('id'),
                        'product_tmpl_id': act_product_template.id,
                        'variant_integrations_data': json.dumps(product.get('integrations'), separators=(',', ':'))
                    }
                    if len(product.get('images')):
                        url = product.get('images')[0]
                        if url:
                            image = base64.b64encode(requests.get(url.strip()).content).replace(b'\n', b'')
                            data['image_variant'] = image

                    if len(product.get('integration')):
                        integrations = []
                        data_external = []
                        list_category = []
                        list_brand = []
                        integration = product.get('integration')
                        integrations.append(product.get('integration').get('id'))

                        data['external_id_integration_ids'] = [(0, 0, {'integration_id': integration.get('id'),
                                                                       'id_external': integration.get(
                                                                           'variant').get('remote_product_id')})]
                        category_or_brands = integration.get('variant').get('properties')
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

                        ids = self.env['omna.integration'].search([('integration_id', 'in', integrations)]).ids
                        data['variant_integration_ids'] = [(6, 0, ids)]
                        # data['external_id_integration_ids'] = [(6, 0, data_external)]

                    act_product = product_obj.with_context(synchronizing=True).create(data)

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
