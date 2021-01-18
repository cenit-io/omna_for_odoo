# -*- coding: utf-8 -*-

import logging, odoo
from datetime import datetime, timezone
import dateutil.parser
from odoo import models, api, exceptions, fields, _
import pytz

_logger = logging.getLogger(__name__)


class PropertiesValuesWizard(models.TransientModel):
    _name = 'properties.values.wizard'
    _inherit = 'omna.api'



    def _get_category_id(self):
        product_template_obj = self.env['product.template']
        product = product_template_obj.search([('id', '=', self.env.context.get('default_product_template_id', False))])
        aux = list(filter(lambda lolo: lolo.integration_id.id == self.env.context.get('integration_id', False), product.category_ids))
        if aux:
            return aux[0]
        else:
            return False



    def _get_category_domain(self):
        product_category_obj = self.env['product.category']
        result = product_category_obj.search([('integration_id', '=', self.env.context.get('integration_id', False)), ('omna_category_id', '!=', False)]).ids
        if result:
            return [('id', 'in', result)]
        else:
            return [('id', '=', -1)]



    def _get_property_primary_domain(self):
        integration_properties_obj = self.env['integration.properties']
        result = integration_properties_obj.search([('integration_id', '=', self.env.context.get('integration_id', False))]).ids
        if result:
            return [('id', 'in', result)]
        else:
            return [('id', '=', -1)]


    def _get_property_value_ids(self):
        integration_properties_obj = self.env['integration.properties']
        product_template_obj = self.env['product.template']
        properties_values_obj = self.env['properties.values']
        omna_integration_obj = self.env['omna.integration']
        result = properties_values_obj.search(['&','|',('product_template_id', '=', self.env.context.get('default_product_template_id', False)),
                                                       ('integration_id', '=', self.env.context.get('integration_id', False)),
                                               ('property_name', '!=', 'category_id')]).ids
        if result:
            return result
        else:
            return []



    # def _get_property_primary_id(self):
    #     integration_properties_obj = self.env['integration.properties']
    #     product_template_obj = self.env['product.template']
    #     properties_values_obj = self.env['properties.values']
    #     omna_integration_obj = self.env['omna.integration']
    #     result = integration_properties_obj.search(['&', '&', ('integration_id', '=', self.env.context.get('integration_id', False)),
    #                                                    ('property_category', '=', 'primary_property'), ('property_name', '=', 'category_id')]).ids
    #     if result:
    #         return result[0]
    #     else:
    #         return False
    #         # product = product_template_obj.search([('id', '=', self.env.context.get('default_product_template_id', False))])
    #         # response = integration_properties_obj.get('products/%s' % product.omna_product_id)
    #         # remote_result = response.get('data').get('integrations')
    #         # lolo = self.env['omna.integration_product'].search([('id', '=', self.env.context.get('integration_product_id', False))])
    #         # lolo.integration_ids.integration_id
    #         # aux = list(filter(lambda person: person['id'] == lolo.integration_ids.integration_id, remote_result))
    #         # if aux:
    #         #     query = """"""
    #         #     for item in aux:
    #         #         temp = item.get('product').get('properties')[0]
    #         #         query += """ INSERT INTO integration_properties (property_name, property_type, integration_id, property_category, property_label, property_required, property_readonly)
    #         #             VALUES ('%s', '%s', '%s', '%s', '%s', %s, %s)
    #         #             RETURNING id; """ % (temp.get('id'), 'string', self.env.context.get('integration_id'), 'primary_property', temp.get('label'), 'false', 'false')
    #         #
    #         #     self.env.cr.execute(query)
    #         #     self.env.cr.commit()
    #         #     return []


    def _get_omna_integration_id(self):
        omna_integration_obj = self.env['omna.integration']
        result = omna_integration_obj.search([('id', '=', self.env.context.get('integration_id', False))]).ids
        if result:
            return result[0]
        else:
            return False



    # property_value_ids = fields.Many2many('properties.values', string='Property List')
    # property_value_primary_ids = fields.Many2many('properties.values', default=_get_property_value_primary_ids, string='Property Primary List')
    # property_primary_id = fields.Many2one('integration.properties', 'Primary Property', default=_get_property_primary_id, domain=_get_property_primary_domain)
    omna_integration_id = fields.Many2one('omna.integration', 'Integration to Link', required=True, default=_get_omna_integration_id)
    category_id = fields.Many2one('product.category', 'Category', required=True, default=_get_category_id, domain=_get_category_domain)
    property_value_ids = fields.Many2many('properties.values', default=_get_property_value_ids, string='Property List')

    @api.onchange('omna_integration_id')
    def _onchange_omna_integration_id(self):
        product_category_obj = self.env['product.category']
        result = product_category_obj.search([('integration_id', '=', self.omna_integration_id.id)]).ids
        if result:
            return {'domain': {'category_id': [('id', 'in', result)]}}
        else:
            return {'domain': {'category_id': [('id', '=', -1)]}}


    def get_properties_product(self):
        integration_properties_obj = self.env['integration.properties']
        product_template_obj = self.env['product.template']
        properties_values_obj = self.env['properties.values']
        omna_integration_obj = self.env['omna.integration']
        integration = omna_integration_obj.search([('id', '=', self.env.context.get('integration_id', False))])
        product = product_template_obj.search([('id', '=', self.env.context.get('default_product_template_id', False))])


        aux2 = list(filter(lambda lolo: lolo.integration_id.id == integration.id, product.category_ids))
        if not aux2:
            product.write({'category_ids': [(4, self.category_id.id)]})
            self.env.cr.commit()

        temp = {
            "data": {
                "properties": [
                    {
                        "id": "category_id",
                        "value": self.category_id.omna_category_id
                    }
                ]
            }
        }

        response = product_template_obj.post('integrations/%s/products/%s' % (integration.integration_id, "PENDING-PUBLISH-FROM-" + product.omna_product_id),temp)
        response = product_template_obj.get('integrations/%s/products/%s' % (integration.integration_id, "PENDING-PUBLISH-FROM-" + product.omna_product_id))


        result = properties_values_obj.search(['&','|',('product_template_id', '=', product.id), ('integration_id', '=', integration.id), ('property_name', '!=', 'category_id')]).ids
        if result:
            self.property_value_ids = result
        else:
            remote_result = response.get('data').get('integration').get('product').get('properties')
            lolo = [x.get('id') for x in remote_result]
            exist_properties = integration_properties_obj.search([('integration_id', '=', integration.id)])
            # aux3 = list(filter(lambda lolo: (lolo.integration_id.id == self.env.context.get('integration_id', False)) and (lolo.property_name == 'category_id'), integration_ids))
            # self.property_primary_id = exist_category
            values_list = []
            # list_options = eval(values.get('options'))
            if not exist_properties:
                if remote_result:
                    query = """"""
                    for item in remote_result:
                        values_list.append({
                            'property_name': item.get('id'),
                            'property_type': item.get('input_type'),
                            'integration_id': integration.id,
                            'property_category': 'primary_property',
                            'property_label': item.get('label'),
                            'property_required': item.get('required'),
                            'property_readonly': item.get('read_only'),
                            'property_options': str(item.get('options')),
                            'property_options_service_path': item.get('options_service_path'),
                            'value_option_ids': [(0, 0, {'option_value': res}) for res in item.get('options')] if item.get('input_type') in ['single_select', 'multi_select', 'enum_input'] else []
                        })
                        # query += """ INSERT INTO integration_properties (property_name, property_type, integration_id, property_category, property_label, property_required, property_readonly)
                        # VALUES ('%s', '%s', '%s', '%s', '%s', %s, %s)
                        # ON CONFLICT DO NOTHING; """ % (item.get('id'), 'string', self.env.context.get('integration_id'), 'primary_property', item.get('label'), 'false', 'false')
                    integration_properties_obj.create(values_list)
                    # self.env.cr.execute(query)
                    self.env.cr.commit()

            integration_ids = integration_properties_obj.search([('integration_id', '=', integration.id), ('property_name', 'in', lolo)])
            values_list.clear()
            if integration_ids:
                query = """"""
                for item in integration_ids:
                    values_list.append({
                        'property_id': item.id,
                        'product_template_id': product.id,
                        'property_value': 'default_value',
                        # 'integration_id': item.integration_id.id,
                        # 'property_name': item.property_name,
                        # 'property_label': item.property_label,
                        # 'property_category': item.property_category,
                        # 'property_options': "Posibles valores a asignar: " + item.property_options,
                        # 'property_options_service_path': "Valores a asignar relacionados en: " + item.property_options_service_path if item.property_options_service_path else ""
                    })
                    # query += """ INSERT INTO properties_values (property_id, product_template_id, property_value, integration_id, property_name, property_label, property_category)
                    #                                     VALUES (%s, %s, '%s', %s, '%s', '%s', '%s')
                    #                                     RETURNING id; """ % (
                    #     item.id, product.id, 'default_value',
                    #     item.integration_id.id, item.property_name, item.property_label, item.property_category)
                properties_values_obj.create(values_list)
                # self.env.cr.execute(query)
                self.env.cr.commit()
                self.property_value_ids = properties_values_obj.search(['&', '|', ('product_template_id', '=', product.id), ('integration_id', '=', integration.id), ('property_name', '!=', 'category_id')]).ids


        form_view_id = self.env.ref('omna.view_properties_values_wizard').id
        # your logics
        return {
            'type': 'ir.actions.act_window',
            'name': 'Property List By Integrations',
            'view_type': 'form',
            'view_mode': 'form',
            'res_model': 'properties.values.wizard',
            'views': [[form_view_id, "form"]],
            # 'domain': [('property_name','!=','category_id')],
            'res_id': self.id,
            'context': self.env.context,
            'target': 'new',
        }


    # @api.onchange('property_primary_id')
    # def _onchange_property_primary_id(self):
    #     integration_properties_obj = self.env['integration.properties']
    #     product_template_obj = self.env['product.template']
    #     properties_values_obj = self.env['properties.values']
    #     omna_integration_obj = self.env['omna.integration']
    #
    #     result = self.env['properties.values'].search([('product_template_id', '=', self.env.context.get('default_product_template_id', False)),
    #                                                    ('integration_id', '=', self.env.context.get('integration_id', False))]).ids
    #     if result:
    #         self.property_value_ids = result
    #     else:
    #         # product = product_template_obj.search([('id', '=', self.env.context.get('default_product_template_id', False))])
    #         # response = integration_properties_obj.get('products/%s' % product.omna_product_id)
    #         # remote_result = response.get('data').get('integrations')[0].get('product').get('properties')
    #         #
    #         # # integration_ids = self.env['integration.properties'].search([('integration_id', '=', self.env.context.get('integration_id', False))])
    #         #
    #         # if remote_result:
    #         #     query = """"""
    #         #     for item in remote_result:
    #         #         query += """ INSERT INTO integration_properties (property_name, property_type, integration_id, property_category, property_label, property_required, property_readonly)
    #         #             VALUES ('%s', '%s', '%s', '%s', '%s', %s, %s)
    #         #             ON CONFLICT DO NOTHING; """ % (item.get('id'), 'string', self.env.context.get('integration_id'), 'primary_property', item.get('label'), 'false', 'false')
    #         #
    #         #     self.env.cr.execute(query)
    #         #     self.env.cr.commit()
    #
    #         integration_ids = self.env['integration.properties'].search([('integration_id', '=', self.env.context.get('integration_id', False))])
    #         if integration_ids:
    #             query = """"""
    #             for item in integration_ids:
    #                 query += """ INSERT INTO properties_values (property_id, product_template_id, property_value, integration_id, property_name, property_label, property_category)
    #                                         VALUES (%s, %s, '%s', %s, '%s', '%s', '%s')
    #                                         RETURNING id; """ % (
    #                 item.id, self.env.context.get('default_product_template_id'), 'default_value',
    #                 item.integration_id.id, item.property_name, item.property_label, item.property_category)
    #
    #                 # query += """ INSERT INTO properties_values (property_id, product_template_id, property_value, integration_id, property_name)
    #                 #     VALUES (%s, %s, '%s', %s, '%s')
    #                 #     RETURNING id; """ % (item.id, self.env.context.get('default_product_template_id'), 'default_value', item.integration_id.id, item.property_name)
    #
    #             self.env.cr.execute(query)
    #             self.env.cr.commit()
    #             complete = self.env.cr.fetchall()
    #             self.property_value_ids = self.env['properties.values'].search([('product_template_id', '=', self.env.context.get('default_product_template_id', False)),
    #                                                    ('integration_id', '=', self.env.context.get('integration_id', False))]).ids


    def save_all_values(self):
        return {'type': 'ir.actions.act_window_close'}



    def publish_product(self):
        integration_properties_obj = self.env['integration.properties']
        product_template_obj = self.env['product.template']
        product_product_obj = self.env['product.product']
        properties_values_obj = self.env['properties.values']
        omna_integration_obj = self.env['omna.integration']
        product = product_template_obj.search([('id', '=', self.env.context.get('default_product_template_id', False))])
        product_variant = product_product_obj.search([('product_tmpl_id', '=', product.id)])
        # product.write({'category_ids': [(4, self.category_id.id)]})
        # self.env.cr.commit()
        #
        # self._onchange_property_primary_id()
        # https: // cenit.io / app / ecapi - v1 / integrations / {integration_id} / products / {remote_product_id}
        # https: // cenit.io / app / ecapi - v1 / integrations / {integration_id} / products / {remote_product_id}
        # https: // cenit.io / app / ecapi - v1 / integrations / {integration_id} / products / {remote_product_id} / variants / {remote_variant_id}
        integration = omna_integration_obj.search([('id', '=', self.env.context.get('integration_id', False))])
        # properties_values = properties_values_obj.search([('product_template_id', '=', product.id), ('integration_id', '=', integration.id)])

        response_variant = product_product_obj.get('integrations/%s/products/%s/variants/%s' % (integration.integration_id, "PENDING-PUBLISH-FROM-" + product.omna_product_id, "PENDING-PUBLISH-FROM-" + product_variant.omna_variant_id))
        response_product = product_template_obj.get('integrations/%s/products/%s' % (integration.integration_id, "PENDING-PUBLISH-FROM-" + product.omna_product_id))

        remote_result = response_product.get('data').get('integration').get('product').get('properties')
        remote_variant_result = response_variant.get('data').get('integration').get('variant').get('properties')
        temp_variant = {"data": {"properties": []}}
        temp = {"data": {"properties": []}}

        data1 = {"data": {"price": 500,
                         "package": {'weight': 10, 'height': 5, 'length': 20, 'width': 25}}}
        data2 = {"data": {"name": "Test Product First",
                          "description": "IPod Nano - 4GB ...",
                          "price": 500,
                          "package": {'weight': 10, 'height': 5, 'length': 20, 'width': 25, "overwrite": False}}}

        response1 = product_product_obj.post('products/%s/variants/%s' % (product.omna_product_id, product_variant.omna_variant_id), data1)
        response2 = product_template_obj.post('products/%s' % (product.omna_product_id), data2)

        # for item in properties_values:
        for item in remote_result:
            if item.get('id') != 'category_id':
                if (not item.get('options')) and (item.get('id') != 'brand'):
                    temp['data']['properties'].append({'id': item.get('id'), 'value': 'default_value'})
                if item.get('id') == 'brand':
                    temp['data']['properties'].append({'id': item.get('id'), 'value': '123582266'})
                if item.get('options'):
                    temp['data']['properties'].append({'id': item.get('id'), 'value': item.get('options')[0]})

        for item in remote_variant_result:
            if item.get('id') != 'category_id':
                if item.get('input_type') == 'date':
                    temp_variant['data']['properties'].append({'id': item.get('id'), 'value': '2021/01/05'})
                if (not item.get('options')) and (item.get('input_type') != 'date'):
                    temp_variant['data']['properties'].append({'id': item.get('id'), 'value': 'default_value'})
                if item.get('options'):
                    temp_variant['data']['properties'].append({'id': item.get('id'), 'value': item.get('options')[0]})

        response1 = product_product_obj.post('integrations/%s/products/%s/variants/%s' % (integration.integration_id, "PENDING-PUBLISH-FROM-" + product.omna_product_id, "PENDING-PUBLISH-FROM-" + product_variant.omna_variant_id), temp_variant)
        response2 = product_template_obj.post('integrations/%s/products/%s' % (integration.integration_id, "PENDING-PUBLISH-FROM-"+product.omna_product_id), temp)

        return {'type': 'ir.actions.act_window_close'}
        # form_view_id = self.env.ref('omna.view_properties_values_wizard').id
        # # your logics
        # return {
        #     'type': 'ir.actions.act_window',
        #     'name': 'Property List By Integrations',
        #     'view_type': 'form',
        #     'view_mode': 'form',
        #     'res_model': 'properties.values.wizard',
        #     'views': [[form_view_id, "form"]],
        #     'res_id': self.id,
        #     'context': self.env.context,
        #     'target': 'new',
        # }
