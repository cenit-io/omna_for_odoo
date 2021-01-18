# -*- coding: utf-8 -*-

import odoo
import datetime
from odoo import models, fields, api, exceptions, tools, _
from odoo.exceptions import UserError
from odoo.tools.image import image_data_uri
from odoo.tools import float_compare, pycompat
from odoo.tools import ImageProcess
import dateutil.parser
import werkzeug
import pytz
import json
import os
import base64
import logging

_logger = logging.getLogger(__name__)



class IntegrationProperties(models.Model):
    _name = 'integration.properties'
    _inherit = 'omna.api'
    _rec_name = 'property_label'


    property_name = fields.Char('Property Name', required=True)
    property_type = fields.Char('Property Type', required=True, default='string')
    integration_id = fields.Many2one('omna.integration', 'Integration', required=True)
    property_category = fields.Selection(selection=[('primary_property', 'Primary'), ('not_primary_property', 'Not Primary')], string='Property Type', required=True, default='primary_property')
    property_label = fields.Char('Property Label', required=True)
    property_required = fields.Boolean('Required Property')
    property_readonly = fields.Boolean('ReadOnly Property')
    property_options = fields.Char('Property Options')
    property_options_service_path = fields.Char('Options Service Path')
    value_option_ids = fields.One2many('properties.values.options', 'property_id', 'Integrations')

    # @api.model
    # def create(self, values):
    #     res = super(IntegrationProperties, self).create(values)
    #     list_values = []
    #     list_options = eval(values.get('options'))
    #     if list_options:
    #         for item in list_options:
    #             list_values.append({'property_id': res, 'option_value': item})
    #         self.env['properties.values.options'].create(list_values)
    #     return res

    def unlink(self):
        self.value_option_ids.unlink()
        return super(IntegrationProperties, self).unlink()



class PropertiesValuesOptions(models.Model):
    _name = 'properties.values.options'
    _inherit = 'omna.api'
    _rec_name = 'option_value'


    property_id = fields.Many2one('integration.properties', string='Property', ondelete='cascade')
    option_value = fields.Char(string='Value', required=True)



class PropertiesValues(models.Model):
    _name = 'properties.values'
    _inherit = 'omna.api'
    # _rec_name = 'topic'


    # def _get_property_selection_value(self):
    #     aux = eval(self.property_options if self.property_options else "[]")
    #     lolo = [(item, item) for item in aux] if aux else []
    #     return lolo


    property_id = fields.Many2one('integration.properties', string='Property', required=True, ondelete='cascade')
    product_template_id = fields.Many2one('product.template', string='Product', required=True, ondelete='cascade')
    property_value = fields.Char(string='Char Value')
    integration_id = fields.Many2one(comodel_name='omna.integration', related='property_id.integration_id', readonly=True, store=True)
    property_name = fields.Char(related='property_id.property_name', store=True)
    property_label = fields.Char(related='property_id.property_label', store=True)
    property_category = fields.Selection(related='property_id.property_category', selection=[('primary_property', 'Primary'), ('not_primary_property', 'Not Primary')], store=True)
    property_options = fields.Char(related='property_id.property_options', store=True)
    property_options_service_path = fields.Char(related='property_id.property_options_service_path', store=True)
    property_type = fields.Char(related='property_id.property_type', store=True)
    property_integer_value = fields.Integer(string='Integer Value')
    property_float_value = fields.Float(string='Float Value')
    property_boolean_value = fields.Boolean(string='Boolean Value')
    property_date_value = fields.Date(string='Date Value')
    # property_selection_value = fields.Selection(selection=_get_property_selection_value, string='Selection Value')
    property_selection_value = fields.Many2one('properties.values.options', string='Selection Value', domain="[('property_id', '=', property_id)]")
    property_rich_text_value = fields.Text(string='Rich Text Value')
    property_multi_selection_value = fields.Many2many('properties.values.options', 'multi_select_value_rel', 'property_value_id', 'option_value_id', string='Multi Selection Value')
    property_category_value = fields.Many2one('product.category', string='Category Value')
    property_brand_value = fields.Many2one('product.brand', string='Brand Value')
    property_display_value = fields.Char(string='Stored Value', compute='_property_display_value')


    @api.depends('property_value', 'property_integer_value', 'property_float_value', 'property_boolean_value', 'property_date_value',
                 'property_selection_value', 'property_rich_text_value', 'property_multi_selection_value', 'property_category_value', 'property_brand_value')
    def _property_display_value(self):
        for record in self:
            if record.property_value:
                record.property_display_value = record.property_value
            if record.property_integer_value:
                record.property_display_value = record.property_integer_value
            if record.property_float_value:
                record.property_display_value = record.property_float_value
            if record.property_boolean_value:
                record.property_display_value = 'Yes' if record.property_boolean_value else 'No'
            if record.property_date_value:
                record.property_display_value = record.property_date_value
            if record.property_selection_value:
                record.property_display_value = record.property_selection_value.option_value
            if record.property_rich_text_value:
                record.property_display_value = record.property_rich_text_value
            if record.property_multi_selection_value:
                record.property_display_value = ', '.join([x.option_value for x in record.property_multi_selection_value])
            if record.property_category_value:
                record.property_display_value = record.property_category_value.name
            if record.property_brand_value:
                record.property_display_value = record.property_brand_value.name




class PropertiesValuesVariant(models.Model):
    _name = 'properties.values.variant'
    _inherit = 'omna.api'
    # _rec_name = 'topic'


    property_id = fields.Many2one('integration.properties', string='Property', required=True)
    product_product_id = fields.Many2one('product.product', string='Product Variant', required=True)
    property_value = fields.Char(string='Value')
    integration_id = fields.Many2one(comodel_name='omna.integration', related='property_id.integration_id', readonly=True, store=True)
    property_name = fields.Char(related='property_id.property_name', store=True)
    property_label = fields.Char(related='property_id.property_label', store=True)
    property_category = fields.Selection(related='property_id.property_category', selection=[('primary_property', 'Primary'), ('not_primary_property', 'Not Primary')], store=True)
    property_options = fields.Char(related='property_id.property_options', store=True)
    property_options_service_path = fields.Char(related='property_id.property_options_service_path', store=True)

    property_type = fields.Char(related='property_id.property_type', store=True)
    property_integer_value = fields.Integer(string='Integer Value')
    property_float_value = fields.Float(string='Float Value')
    property_boolean_value = fields.Boolean(string='Boolean Value')
    property_date_value = fields.Date(string='Date Value')
    # property_selection_value = fields.Selection(selection=_get_property_selection_value, string='Selection Value')
    property_selection_value = fields.Many2one('properties.values.options', string='Selection Value',
                                               domain="[('property_id', '=', property_id)]")
    property_rich_text_value = fields.Text(string='Rich Text Value')
    property_multi_selection_value = fields.Many2many('properties.values.options', 'multi_select_value_variant_rel',
                                                      'property_value_id', 'option_value_id',
                                                      string='Multi Selection Value')
    property_category_value = fields.Many2one('product.category', string='Category Value')
    property_brand_value = fields.Many2one('product.brand', string='Brand Value')
    property_display_value = fields.Char(string='Stored Value', compute='_property_display_value')

    @api.depends('property_value', 'property_integer_value', 'property_float_value', 'property_boolean_value',
                 'property_date_value', 'property_selection_value', 'property_rich_text_value',
                 'property_multi_selection_value', 'property_category_value', 'property_brand_value')
    def _property_display_value(self):
        for record in self:
            if record.property_value:
                record.property_display_value = record.property_value
            if record.property_integer_value:
                record.property_display_value = record.property_integer_value
            if record.property_float_value:
                record.property_display_value = record.property_float_value
            if record.property_boolean_value:
                record.property_display_value = 'Yes' if record.property_boolean_value else 'No'
            if record.property_date_value:
                record.property_display_value = record.property_date_value
            if record.property_selection_value:
                record.property_display_value = record.property_selection_value.option_value
            if record.property_rich_text_value:
                record.property_display_value = record.property_rich_text_value
            if record.property_multi_selection_value:
                record.property_display_value = ', '.join(
                    [x.option_value for x in record.property_multi_selection_value])
            if record.property_category_value:
                record.property_display_value = record.property_category_value.name
            if record.property_brand_value:
                record.property_display_value = record.property_brand_value.name