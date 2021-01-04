# -*- coding: utf-8 -*-
import json
from odoo import models, api, _, fields
from odoo.exceptions import ValidationError
from odoo.exceptions import *


class WizardCreateVariant(models.TransientModel):
    _name = "wizard.create.variant"
    _description = "Create a New Variant"

    omna_product_id = fields.Char("Product identifier in OMNA")
    omna_variant_id = fields.Char("Variant identifier in OMNA")
    integration_ids = fields.Many2many('omna.integration', string='Integrations')
    lst_price = fields.Float('Price', default=0.00)
    name = fields.Char("Name")
    description = fields.Text('Description')
    default_code = fields.Char('Code')
    standard_price = fields.Float('Cost Price', default=0.00)
    product_template_id = fields.Many2one('product.template', 'Product Template')
    # external_id_integration_ids = fields.Many2many('omna.variant.integration.external.id',
    #                                               string='External Id by Integration')

    def create_variant(self):
        self.ensure_one()
        omna_variant_id = ''
        omna_template_id = ''
        fields_readed = self.read(['omna_product_id', 'omna_variant_id', 'integration_ids', 'lst_price', 'name', 'description', 'default_code', 'standard_price', 'product_template_id'])[0]
        id, omna_product_id, omna_variant_id, integration_ids, lst_price, name, description, default_code, standard_price, product_template_id = fields_readed.values()
        product_template_ids = self.env[self._context.get('active_model')].browse(self._context.get('active_ids'))
        for product_template in product_template_ids:
            if not omna_product_id:
                omna_product_id = product_template.omna_product_id

            if omna_product_id:
                data = {
                    # 'name': name,
                    # 'description': description,
                    'sku': default_code,
                    'price': lst_price,
                    'original_price': standard_price,
                    'quantity': 0,
                }
                # values = {}
                # values['data'] = data

                response = self.env['omna.api'].post('products/%s/variants' % omna_product_id, {'data': data})
                # response = self.env['omna.api'].post('products/%s/variants' % omna_product_id, data)
                if response.get('data').get('id'):
                    product = response.get('data')
                    omna_variant_id = product.get('id')
                    # integrations = product_template_id.external_id_integration_ids.mapped('integration_id')
                    # integrations = product_template.external_id_integration_ids.mapped('integration_id')
                    integrations = product_template.integration_ids.mapped('integration_ids')
                    # if not integrations:
                    #     raise ValidationError("El producto: %s no tiene integracion disponible, imposible vincularlo." % (product_template.name))
                    data_external = []
                    list_category = []
                    list_brand = []
                    if product.get('integrations'):
                        for integration in product.get('integrations'):
                            new_external = self.env['omna.variant.integration.external.id'].create(
                                    {'integration_id': integration.get('id'),
                                     'id_external': integration.get('variant').get('remote_variant_id')})
                            data_external.append(new_external.id)

                            integration_id = self.env['omna.integration'].search(
                                [('integration_id', '=', integration.get('id'))])

                            category_or_brands = integration.get('product').get('properties')
                            for cat_br in category_or_brands:
                                if (cat_br.get('label') == 'Category') and (cat_br.get('options')):
                                    category_id = cat_br.get('options')[0]['id']
                                    category_name = cat_br.get('options')[0]['name']

                                    arr = category_name.split('>')
                                    category_id = category_id
                                    category_obj = self.env['product.category']
                                    c_tree = self.category_tree(arr, False, category_id, integration_id.id,
                                                                category_obj, list_category)

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
                    p = self.env['product.product'].create({
                            'name': name,
                            # 'description': product.get('description'),
                            'description': description,
                            'lst_price': product.get('price'),
                            'default_code': product.get('sku'),
                            # 'standard_price': product.get('cost_price'),
                            'standard_price': standard_price,
                            # 'quantity': product.get('quantity'),
                            'quantity': 0,
                            'omna_variant_id': product.get('id'),
                            # 'product_tmpl_id': product_template_id.id,
                            'product_tmpl_id': product_template.id,
                            'variant_integrations_data': json.dumps(product.get('integrations'), separators=(',', ':')),
                            'external_id_integration_ids': [(6, 0, data_external)],
                            'category_ids': [(6, 0, list_category)] if 'list_category' else False,
                            'brand_ids': [(6, 0, list_brand)] if 'list_brand' else False,
                            'variant_integration_ids': [(6, 0, integration_ids)]
                    })

                    if integrations:
                        data2 = {
                            'integration_ids': integrations.mapped('integration_id'),
                        }
                        result = self.env['omna.api'].put('products/%s/variants/%s' %(omna_product_id, omna_variant_id), {'data':data2})
                        self.env.user.notify_channel('warning', _(
                            'The task to export the order have been created, please go to "System\Tasks" to check out the task status.'),
                                                     _("Information"), True)

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


