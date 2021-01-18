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


def omna_id2real_id(omna_id):
    if omna_id and isinstance(omna_id, str) and len(omna_id.split('-')) == 2:
        res = [bit for bit in omna_id.split('-') if bit]
        return res[1]
    return omna_id


class OmnaIntegration(models.Model):
    _name = 'omna.integration'
    _inherit = ['omna.api']

    @api.model
    def _get_integrations_channel_selection(self):
        try:
            response = self.get('available/integrations/channels', {})
            selection = []
            for channel in response.get('data'):
                selection.append((channel.get('name'), channel.get('title')))
            return selection
        except Exception as e:
            return []

    @api.model
    def _current_tenant(self):
        current_tenant = self.env['omna.tenant'].search([('id', '=', self.env.user.context_omna_current_tenant.id)],
                                                        limit=1)
        if current_tenant:
            return current_tenant.id
        else:
            return None

    omna_tenant_id = fields.Many2one('omna.tenant', 'Tenant', required=True, default=_current_tenant)
    name = fields.Char('Name', required=True)
    channel = fields.Selection(selection=_get_integrations_channel_selection, string='Channel', required=True)
    integration_id = fields.Char(string='Integration ID', required=True, index=True)
    authorized = fields.Boolean('Authorized', required=True, default=False)
    # image: all image fields are base64 encoded and PIL-supported
    image = fields.Binary(
        "Image", attachment=True,
        help="This field holds the image used as image for the product, limited to 1024x1024px.")
    image_medium = fields.Binary(
        "Medium-sized image", attachment=True,
        help="Medium-sized image of the product. It is automatically "
             "resized as a 128x128px image, with aspect ratio preserved, "
             "only when the image exceeds one of those sizes. Use this field in form views or some kanban views.")
    image_small = fields.Binary(
        "Small-sized image", attachment=True,
        help="Small-sized image of the product. It is automatically "
             "resized as a 64x64px image, with aspect ratio preserved. "
             "Use this field anywhere a small image is required.")

    @api.model
    def _get_logo(self, channel):
        if 'Lazada' in channel:
            logo = 'static' + os.path.sep + 'src' + os.path.sep + 'img' + os.path.sep + 'lazada_logo.png'
        elif 'Qoo10' in channel:
            logo = 'static' + os.path.sep + 'src' + os.path.sep + 'img' + os.path.sep + 'qoo10_logo.png'
        elif 'Shopee' in channel:
            logo = 'static' + os.path.sep + 'src' + os.path.sep + 'img' + os.path.sep + 'shopee_logo.png'
        elif 'Shopify' in channel:
            logo = 'static' + os.path.sep + 'src' + os.path.sep + 'img' + os.path.sep + 'shopify_logo.png'
        elif 'MercadoLibre' in channel:
            logo = 'static' + os.path.sep + 'src' + os.path.sep + 'img' + os.path.sep + 'mercadolibre_logo.png'
        else:
            logo = 'static' + os.path.sep + 'src' + os.path.sep + 'img' + os.path.sep + 'marketplace_placeholder.jpg'
        return logo

    @api.model
    def create(self, vals_list):

        if 'image' not in vals_list:
            logo = self._get_logo(vals_list['channel'])
            path = os.path.join(os.path.abspath(os.path.dirname(os.path.abspath(__file__)) + os.path.sep + '..'), logo)
            with open(path, 'r+b') as fd:
                res = fd.read()
                if res:
                    image = base64.b64encode(res).replace(b'\n', b'')
                    vals_list['image'] = image

        image = ImageProcess(vals_list['image'])
        # w, h = image.image.size
        # square_size = w if w > h else h
        # image.crop_resize(square_size, square_size)
        # image.image = image.image.resize((1024, 1024))
        # image.operationsCount += 1
        vals_list['image'] = image.image_base64(output_format='PNG')

        # tools.image_resize_images(vals_list)

        if not self._context.get('synchronizing'):
            self.check_access_rights('create')
            data = {
                'name': vals_list['name'],
                'channel': vals_list['channel']
            }

            response = self.post('integrations', {'data': data})
            if response.get('data').get('id'):
                vals_list['integration_id'] = response.get('data').get('id')
                return super(OmnaIntegration, self).create(vals_list)
            else:
                raise exceptions.AccessError(_("Error trying to push integration to Omna's API."))
        else:
            return super(OmnaIntegration, self).create(vals_list)

    def write(self, vals):
        if 'image' not in vals:
            logo = self._get_logo(vals['channel'])
            path = os.path.join(os.path.abspath(os.path.dirname(os.path.abspath(__file__)) + os.path.sep + '..'), logo)
            with open(path, 'r+b') as fd:
                res = fd.read()
                if res:
                    image = base64.b64encode(res).replace(b'\n', b'')
                    vals['image'] = image

        image = ImageProcess(vals['image'])
        # w, h = image.image.size
        # square_size = w if w > h else h
        # image.crop_resize(square_size, square_size)
        image.image = image.image.resize((1024, 1024))
        # image.operationsCount += 1
        vals['image'] = image.image_base64(output_format='PNG')

        # tools.image_resize_images(vals)

        return super(OmnaIntegration, self).write(vals)

    def unlink(self):
        self.check_access_rights('unlink')
        self.check_access_rule('unlink')
        for rec in self:
            response = rec.delete('integrations/%s' % rec.integration_id)
        return super(OmnaIntegration, self).unlink()

    def unauthorize(self):
        for integration in self:
            self.delete('integrations/%s/authorize' % integration.integration_id)
        return self.write({'authorized': False})

    def authorize(self):
        self.ensure_one()
        omna_api_url = self.env['ir.config_parameter'].sudo().get_param(
            "omna_odoo.cenit_url", default='https://cenit.io/app/ecapi-v1'
        )
        redirect = self.env['ir.config_parameter'].sudo().get_param(
            'web.base.url') + '/omna/integrations/authorize/' + self.integration_id
        path = 'integrations/%s/authorize' % self.integration_id
        payload = self._sign_request(path, {'redirect_uri': redirect})
        authorize_url = '%s/%s?%s' % (omna_api_url, path, werkzeug.urls.url_encode(payload))
        return {
            'type': 'ir.actions.act_url',
            'url': authorize_url,
            'target': 'self'
        }


class OmnaWebhook(models.Model):
    _name = 'omna.webhook'
    _inherit = 'omna.api'
    _rec_name = 'topic'

    @api.model
    def _get_webhook_topic_selection(self):
        try:
            response = self.get('webhooks/topics', {})
            selection = []
            for topic in response.get('data'):
                selection.append((topic.get('topic'), topic.get('title')))
            return selection
        except Exception as e:
            return []

    @api.model
    def _current_tenant(self):
        current_tenant = self.env['omna.tenant'].search([('id', '=', self.env.user.context_omna_current_tenant.id)],
                                                        limit=1)
        if current_tenant:
            return current_tenant.id
        else:
            return None

    omna_tenant_id = fields.Many2one('omna.tenant', 'Tenant', required=True, default=_current_tenant)
    omna_webhook_id = fields.Char("Webhooks identifier in OMNA", index=True)
    topic = fields.Selection(selection=_get_webhook_topic_selection, string='Topic', required=True)
    address = fields.Char('Address', required=True)
    integration_id = fields.Many2one('omna.integration', 'Integration', required=True)

    @api.model
    def create(self, vals_list):
        if not self._context.get('synchronizing'):
            integration = self.env['omna.integration'].search([('id', '=', vals_list['integration_id'])], limit=1)
            data = {
                'integration_id': integration.integration_id,
                'topic': vals_list['topic'],
                'address': vals_list['address'],
            }
            response = self.post('webhooks', {'data': data})
            if response.get('data').get('id'):
                vals_list['omna_webhook_id'] = response.get('data').get('id')
                return super(OmnaWebhook, self).create(vals_list)
            else:
                raise exceptions.AccessError(_("Error trying to push webhook to Omna's API."))
        else:
            return super(OmnaWebhook, self).create(vals_list)

    def write(self, vals):
        self.ensure_one()
        if not self._context.get('synchronizing'):
            if 'integration_id' in vals:
                integration = self.env['omna.integration'].search([('id', '=', vals['integration_id'])], limit=1)
            else:
                integration = self.env['omna.integration'].search([('id', '=', self.integration_id.id)], limit=1)
                data = {
                    'address': vals['address'] if 'address' in vals else self.address,
                    'integration_id': integration.integration_id,
                    'topic': vals['topic'] if 'topic' in vals else self.topic
                }
            response = self.post('webhooks/%s' % self.omna_webhook_id, {'data': data})
            if response.get('data').get('id'):
                vals['omna_webhook_id'] = response.get('data').get('id')
                return super(OmnaWebhook, self).write(vals)
            else:
                raise exceptions.AccessError(_("Error trying to update webhook in Omna's API."))
        else:
            return super(OmnaWebhook, self).write(vals)

    def unlink(self):
        self.check_access_rights('unlink')
        self.check_access_rule('unlink')
        for rec in self:
            response = rec.delete('webhooks/%s' % rec.omna_webhook_id)
        return super(OmnaWebhook, self).unlink()


class OmnaFlow(models.Model):
    _name = 'omna.flow'
    _inherit = 'omna.api'
    _rec_name = 'type'

    @api.model
    def _get_flow_types(self):
        try:
            response = self.get('flows/types', {})
            selection = []
            for type in response.get('data'):
                selection.append((type.get('type'), type.get('title')))
            return selection
        except Exception as e:
            return []

    @api.model
    def _current_tenant(self):
        current_tenant = self.env['omna.tenant'].search([('id', '=', self.env.user.context_omna_current_tenant.id)],
                                                        limit=1)
        if current_tenant:
            return current_tenant.id
        else:
            return None

    omna_tenant_id = fields.Many2one('omna.tenant', 'Tenant', required=True, default=_current_tenant)
    integration_id = fields.Many2one('omna.integration', 'Integration', required=True)
    type = fields.Selection(selection=_get_flow_types, string='Type', required=True)
    start_date = fields.Datetime("Start Date", help='Select date and time')
    end_date = fields.Date("End Date")
    days_of_week = fields.Many2many('omna.filters', 'omna_flow_days_of_week_rel', 'flow_id', 'days_of_week_id',
                                    domain=[('type', '=', 'dow')])
    weeks_of_month = fields.Many2many('omna.filters', 'omna_flow_weeks_of_month_rel', 'flow_id', 'weeks_of_month_id',
                                      domain=[('type', '=', 'wom')])
    months_of_year = fields.Many2many('omna.filters', 'omna_flow_months_of_year_rel', 'flow_id', 'months_of_year_id',
                                      domain=[('type', '=', 'moy')])
    omna_id = fields.Char('OMNA Workflow ID', index=True)
    active = fields.Boolean('Active', default=True, readonly=True)

    def start(self):
        for flow in self:
            self.get('flows/%s/start' % flow.omna_id, {})
        self.env.user.notify_channel('warning', _(
            'The task to execute the workflow have been created, please go to "System\Tasks" to check out the task status.'),
                                     _("Information"), True)
        return {'type': 'ir.actions.act_window_close'}

    def toggle_status(self):
        for flow in self:
            self.get('flows/%s/toggle/scheduler/status' % flow.omna_id, {})

        self.env.user.notify_channel('warning', _('The workflow\'s status have been changed.'), _("Information"), True)
        return {'type': 'ir.actions.act_window_close'}

    @api.model
    def create(self, vals):
        if not self._context.get('synchronizing'):
            integration = self.env['omna.integration'].search([('id', '=', vals.get('integration_id'))], limit=1)
            data = {
                "integration_id": integration.integration_id,
                "type": vals.get('type'),
                "scheduler": {}
            }

            if 'start_date' in vals:
                start_date = datetime.datetime.strptime(vals.get('start_date'), "%Y-%m-%d %H:%M:%S")
                data['scheduler']['start_date'] = start_date.date().strftime("%Y-%m-%d")
                data['scheduler']['time'] = start_date.time().strftime("%H:%M")
            if 'end_date' in vals:
                end_date = datetime.datetime.strptime(vals.get('end_date'), "%Y-%m-%d")
                data['scheduler']['end_date'] = end_date.strftime("%Y-%m-%d")
            if 'days_of_week' in vals:
                dow = []
                days = self.env['omna.filters'].search(
                    [('type', '=', 'dow'), ('id', 'in', vals.get('days_of_week')[0][2])])
                for day in days:
                    dow.append(day.name)
                data['scheduler']['days_of_week'] = dow
            if 'weeks_of_month' in vals:
                wom = []
                weeks = self.env['omna.filters'].search(
                    [('type', '=', 'wom'), ('id', 'in', vals.get('weeks_of_month')[0][2])])
                for week in weeks:
                    wom.append(week.name)
                data['scheduler']['weeks_of_month'] = wom
            if 'months_of_year' in vals:
                moy = []
                months = self.env['omna.filters'].search(
                    [('type', '=', 'moy'), ('id', 'in', vals.get('months_of_year')[0][2])])
                for month in months:
                    moy.append(month.name)
                data['scheduler']['months_of_year'] = moy

            response = self.post('flows', {'data': data})
            if 'id' in response.get('data'):
                vals['omna_id'] = response.get('data').get('id')
                return super(OmnaFlow, self).create(vals)
            else:
                raise exceptions.AccessError(_("Error trying to push the workflow to Omna."))
        else:
            return super(OmnaFlow, self).create(vals)

    def write(self, vals):
        self.ensure_one()
        if not self._context.get('synchronizing'):
            if 'type' in vals:
                raise UserError(
                    "You cannot change the type of a worflow. Instead you should delete the current workflow and create a new one of the proper type.")
            if 'integration_id' in vals:
                raise UserError(
                    "You cannot change the integration of a worflow. Instead you should delete the current workflow and create a new one of the proper type.")

            data = {
                "scheduler": {}
            }

            if 'start_date' in vals:
                start_date = datetime.datetime.strptime(vals.get('start_date'), "%Y-%m-%d %H:%M:%S")
                data['scheduler']['start_date'] = start_date.date().strftime("%Y-%m-%d")
                data['scheduler']['time'] = start_date.time().strftime("%H:%M")
            if 'end_date' in vals:
                end_date = datetime.datetime.strptime(vals.get('end_date'), "%Y-%m-%d")
                data['scheduler']['end_date'] = end_date.strftime("%Y-%m-%d")
            if 'days_of_week' in vals:
                dow = []
                days = self.env['omna.filters'].search(
                    [('type', '=', 'dow'), ('id', 'in', vals.get('days_of_week')[0][2])])
                for day in days:
                    dow.append(day.name)
                data['scheduler']['days_of_week'] = dow
            if 'weeks_of_month' in vals:
                wom = []
                weeks = self.env['omna.filters'].search(
                    [('type', '=', 'wom'), ('id', 'in', vals.get('weeks_of_month')[0][2])])
                for week in weeks:
                    wom.append(week.name)
                data['scheduler']['weeks_of_month'] = wom
            if 'months_of_year' in vals:
                moy = []
                months = self.env['omna.filters'].search(
                    [('type', '=', 'moy'), ('id', 'in', vals.get('months_of_year')[0][2])])
                for month in months:
                    moy.append(month.name)
                data['scheduler']['months_of_year'] = moy

            response = self.post('flows/%s' % self.omna_id, {'data': data})
            if 'id' in response.get('data'):
                return super(OmnaFlow, self).write(vals)
            else:
                raise exceptions.AccessError(_("Error trying to update the workflow in Omna."))
        else:
            return super(OmnaFlow, self).write(vals)

    def unlink(self):
        self.check_access_rights('unlink')
        self.check_access_rule('unlink')
        for flow in self:
            flow.delete('flows/%s' % flow.omna_id)
        return super(OmnaFlow, self).unlink()


class OmnaIntegrationProduct(models.Model):
    _name = 'omna.integration_product'
    _inherit = 'omna.api'


    def _get_product_template_id(self):
        return self.env.context.get('default_product_template_id', False)


    def _compute_state(self):
        if self.integration_ids in self.product_template_id.integration_linked_ids:
            self.state = 'linked'
        else:
            self.state = 'unlinked'



    product_template_id = fields.Many2one('product.template', 'Product', required=True, ondelete='cascade', default=lambda self: self.env.context.get('default_product_template_id', False))
    # product_template_id = fields.Many2one('product.template', 'Product', required=True, ondelete='cascade', default=lambda self: self._get_product_template_id())
    # integration_ids = fields.Many2many('omna.integration', 'omna_integration_integration_rel', 'integration_product_id',
    #                                    'integration_id', 'OMNA Integrations', required=True)
    integration_ids = fields.Many2one('omna.integration', 'OMNA Integration', required=True)
    link_with_its_variants = fields.Selection([
        ('NONE', 'NONE'),
        ('SELECTED', 'SELECTED'),
        ('NEW', 'NEW'),
        ('ALL', 'ALL')], default='ALL', required=True)
    delete_from_integration = fields.Boolean("Delete from Integration", default=False,
                                             help="Set whether the product should be removed from the remote integration source.")
    state = fields.Selection([('linked', 'LINKED'), ('unlinked', 'UNLINKED')], default='unlinked', compute='_compute_state')



    @api.model
    def create(self, vals_list):
        res = super(OmnaIntegrationProduct, self).create(vals_list)
        # try:
        #     # integrations = [integration.integration_id for integration in res.integration_ids]
        #     integrations = [res.integration_ids.integration_id]
        #     data = {
        #         'data': {
        #             'integration_ids': integrations,
        #             'link_with_its_variants': res.link_with_its_variants
        #         }
        #     }
        #     self.put('products/%s' % res.product_template_id.omna_product_id, data)
        #     # https: // cenit.io / app / ecapi - v1 / products / {product_id}
        #     # response = self.get('products/%s' % res.product_template_id.omna_product_id)
        #     # print(response)
        #     # llamar al endpoint https://doc-api.omna.io/api-spec/#operation/get_product_beta_
        #
        return res
        # except Exception:
        #     raise exceptions.AccessError(_("Error trying to update products in Omna's API."))

    # @api.multi
    # def write(self, vals):
    #     return super(OmnaIntegrationProduct, self).write(vals)

    def unlink(self):
        return super(OmnaIntegrationProduct, self).unlink()
        # try:
        #     for intg_product in self:
        #         # integrations = [integration.integration_id for integration in intg_product.integration_ids]
        #         integrations = [intg_product.integration_ids.integration_id]
        #         data = {
        #             'data': {
        #                 'integration_ids': integrations,
        #                 'delete_from_integration': intg_product.delete_from_integration
        #             }
        #         }
        #         self.patch('products/%s' % intg_product.product_template_id.omna_product_id, data)
        #
        #     return super(OmnaIntegrationProduct, self).unlink()
        # except Exception:
        #     raise exceptions.AccessError(_("Error trying to update products in Omna's API."))


    def launch_wizard_list(self):
        view_id = self.env.ref('omna.view_properties_values_wizard').id
        context = dict(
            self.env.context,
            integration_id=self.integration_ids.id,
            integration_product_id=self.id,
        )

        return {
            'name': 'Property List By Integrations',
            'type': 'ir.actions.act_window',
            'view_mode': 'form',
            'res_model': 'properties.values.wizard',
            'view_id': view_id,
            'views': [(view_id, 'form')],
            'target': 'new',
            'context': context,
        }

    def action_link(self):
        try:
            # integrations = [integration.integration_id for integration in res.integration_ids]
            integrations = [self.integration_ids.integration_id]
            data = {
                'data': {
                    'integration_ids': integrations,
                    'link_with_its_variants': self.link_with_its_variants
                }
            }

            response = self.put('products/%s' % self.product_template_id.omna_product_id, data)

            # external_id_integration_ids

            # new_external = self.env['omna.template.integration.external.id'].create(
            #     {'integration_id': self.integration_ids.integration_id,
            #      'id_external': self.product_template_id.omna_product_id})
            # self.env.cr.commit()
            # vals_list['external_id_integration_ids'] = [(6, 0, data_external)]
            self.product_template_id.write({'integration_linked_ids': [(4, self.integration_ids.id)]})
            self.env.cr.commit()

            return self
        except Exception:
            raise exceptions.AccessError(_("Error trying to update products in Omna's API."))



    def action_unlink(self):
        try:
            # integrations = [integration.integration_id for integration in res.integration_ids]
            temp_obj = self.env['omna.template.integration.external.id']
            integrations = [self.integration_ids.integration_id]
            data = {
                'data': {
                    'integration_ids': integrations,
                    'delete_from_integration': self.delete_from_integration
                }
            }

            response = self.patch('products/%s' % self.product_template_id.omna_product_id, data)

            # aux = temp_obj.search([('integration_id', '=', self.integration_ids.integration_id), ('product_template_id', '=', self.product_template_id.omna_product_id)])

            self.product_template_id.write({'integration_ids': [(2, self.id)],
                                            'integration_linked_ids': [(3, self.integration_ids.id)]})
            self.env.cr.commit()

            return self
        except Exception:
            raise exceptions.AccessError(_("Error trying to update products in Omna's API."))


class TemplateIntegrationExternalId(models.Model):
    _name = 'omna.template.integration.external.id'
    _inherit = ['omna.api']

    id_external = fields.Char('External Id', required=True)
    integration_id = fields.Char('Integration Id', required=True)
    product_template_id = fields.Many2one('product.template', string='Product Template',
                                          ondelete='cascade')


# class VariantIntegrationExternalId(models.Model):
#     _name = 'omna.variant.integration.external.id'
#     # _inherit = ['omna.api']
#
#     id_external = fields.Char('External Id', required=True)
#     integration_id = fields.Char('Integration Id', required=True)
#     product_variant_id = fields.Many2one('product.template', 'Product Variant', ondelete='cascade')


class ProductTemplate(models.Model):
    _name = 'product.template'
    _inherit = ['product.template', 'omna.api']

    @api.model
    def _current_tenant(self):
        current_tenant = self.env['omna.tenant'].search([('id', '=', self.env.user.context_omna_current_tenant.id)],
                                                        limit=1)
        if current_tenant:
            return current_tenant.id
        else:
            return None

    omna_tenant_id = fields.Many2one('omna.tenant', 'Tenant', default=_current_tenant)
    # omna_product_id = fields.Many2one('omna.integration', 'Integration ID')
    omna_product_id = fields.Char("Product identifier in OMNA", index=True)
    integration_ids = fields.One2many('omna.integration_product', 'product_template_id', 'Integrations')
    integrations_data = fields.Char('Integrations data')
    no_create_variants = fields.Boolean('Do not create variants automatically', default=True)
    external_id_integration_ids = fields.One2many('omna.template.integration.external.id', 'product_template_id',
                                                  string='External Id by Integration')
    integration_linked_ids = fields.Many2many('omna.integration', 'omna_integration_product_template_rel', string='Linked Integrations')
    # variant_external_id_integration_ids = fields.One2many('omna.variant.integration.external.id', 'product_variant_id',
    #                                               string='External Id by Integration')

    brand_ids = fields.Many2many('product.brand', string='Brand')
    category_ids = fields.Many2many('product.category', string='Category')

    def _create_variant_ids(self):
        if not self.no_create_variants:
            return super(ProductTemplate, self)._create_variant_ids()
        return True

    @api.model
    def create(self, vals_list):
        if not self._context.get('synchronizing'):
            data = {
                'name': vals_list['name'],
                'price': vals_list['list_price'],
                'description': vals_list['description'] or 'description',
                # 'category': categ.omna_category_id,
                # 'brand': brand.omna_brand_id,
            }
            # TODO Send image as data url to OMNA when supported
            # if 'image' in vals_list:
            #     data['images'] = [image_data_uri(str(vals_list['image']).encode('utf-8'))]
            response = self.post('products', {'data': data})
            if response.get('data').get('id'):
                product = response.get('data')
                vals_list['omna_product_id'] = response.get('data').get('id')
                data_external = []
                integrations = []
                list_category = []
                list_brand = []
                for integration in product.get('integrations'):
                    integrations.append(integration.get('id'))
                    new_external = self.env['omna.template.integration.external.id'].create(
                        {'integration_id': integration.get('id'),
                         'id_external': integration.get('product').get('remote_product_id')})
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

                vals_list['category_ids'] = [(6, 0, list_category)]
                vals_list['brand_ids'] = [(6, 0, list_brand)]

                omna_integration = self.env['omna.integration'].search([('integration_id', 'in', integrations)])
                for integration in omna_integration:
                    data['integration_ids'] = [(0, 0, {'integration_ids': [(4, integration.id, 0)]})]
                vals_list['external_id_integration_ids'] = [(6, 0, data_external)]
                return super(ProductTemplate, self).create(vals_list)
            else:
                raise exceptions.AccessError(_("Error trying to push product to Omna's API."))
        else:
            return super(ProductTemplate, self).create(vals_list)

    def write(self, vals):
        if not self._context.get('synchronizing'):
            for record in self:
                if 'name' in vals or 'list_price' in vals or 'description' in vals:
                    if "create_product_product" in self._context:
                        vals['name'] = record.name
                    data = {
                        'name': vals['name'] if 'name' in vals else record.name,
                        'price': vals['list_price'] if 'list_price' in vals else record.list_price,
                        'description': vals['description'] if 'description' in vals else (record.description or ''),
                        # 'category': categ.omna_category_id,
                        # 'brand': brand.omna_brand_id,
                    }
                    # TODO Send image as data url to OMNA when supported
                    # if 'image' in vals:
                    #     data['images'] = [image_data_uri(str(vals['image']).encode('utf-8'))]
                    response = self.post('products/%s' % record.omna_product_id, {'data': data})
                    if not response.get('data').get('id'):
                        raise exceptions.AccessError(_("Error trying to update products in Omna's API."))

                if 'integrations_data' in vals:
                    old_data = json.loads(record.integrations_data)
                    new_data = json.loads(vals['integrations_data'])
                    if old_data != new_data:
                        for integration in old_data:
                            integration_new_data = False
                            for integration_new in new_data:
                                if integration_new['id'] == integration['id']:
                                    integration_new_data = integration_new
                                    break
                            if integration_new_data and integration_new_data != integration:
                                integration_data = {'properties': []}
                                list_category = []
                                list_brand = []
                                integration_id = self.env['omna.integration'].search(
                                    [('integration_id', '=', integration_new['id'])])
                                for field in integration_new_data['product']['properties']:
                                    if (field.get('label') == 'Category') and (field.get('options')):
                                        category_id = field.get('options')[0]['id']
                                        category_name = field.get('options')[0]['name']
                                        arr = category_name.split('>')
                                        category_id = category_id
                                        category_obj = self.env['product.category']
                                        c_tree = self.category_tree(arr, False, category_id, integration_id.id,
                                                                    category_obj, list_category)

                                    if (field.get('label') == 'Brand'):
                                        brand_id = field.get('id')
                                        brand_name = field.get('value')
                                        brands = self.env['product.brand'].search(
                                            [('integration_id', '=', integration_id.id), '|', ('name', '=', brand_name),
                                             ('omna_brand_id', '=', brand_id)], limit=1)
                                        if brands:
                                            brands.write(
                                                {'name': brand_name, 'omna_brand_id': brand_id})
                                        else:
                                            brands = self.env['product.brand'].create(
                                                {'name': brand_name, 'omna_brand_id': brand_id,
                                                 'integration_id': integration_id.id})
                                        list_brand.append(brands.id)

                                    integration_data['properties'].append(
                                        {'id': field['id'], 'value': field['value'], 'label': field['label']})

                                vals['category_ids'] = [(6, 0, list_category)]
                                vals['brand_ids'] = [(6, 0, list_brand)]

                                response = self.post(
                                    'integrations/%s/products/%s' % (
                                    integration['id'], integration['product']['remote_product_id']),
                                    {'data': integration_data})
                                if not response.get('data').get('id'):
                                    raise exceptions.AccessError(
                                        _("Error trying to update products in Omna's API."))

            return super(ProductTemplate, self).write(vals)
        else:
            return super(ProductTemplate, self).write(vals)

    def unlink(self):
        self.check_access_rights('unlink')
        self.check_access_rule('unlink')
        for rec in self:
            integrations = [integration.integration_ids.integration_id for integration in rec.integration_ids]
            data = {
                "integration_ids": integrations,
                "delete_from_integration": True,
                "delete_from_omna": True
            }
            response = rec.delete('products/%s' % rec.omna_product_id, {'data': data})
        return super(ProductTemplate, self).unlink()

    def action_create_variant(self):
        self.ensure_one()
        integrations = self.external_id_integration_ids.mapped('integration_id')

        # omna_integrations = self.env['omna.integration'].search([('integration_id', 'in', integrations)])
        omna_integrations = self.integration_ids.mapped('integration_ids')

        return {
            'name': _('Create Variant'),
            'type': 'ir.actions.act_window',
            'res_model': 'wizard.create.variant',
            'view_type': 'form',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_omna_product_id': self.omna_product_id,
                'default_integration_ids': omna_integrations.ids,
                'default_product_template_id': self.id,
            }
        }

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


class ProductProduct(models.Model):
    _name = 'product.product'
    _inherit = ['product.product', 'omna.api']

    lst_price = fields.Float(compute=False, inverse=False)
    omna_variant_id = fields.Char("Product Variant identifier in OMNA", index=True)
    variant_integration_ids = fields.Many2many('omna.integration', 'omna_product_integration_rel', 'product_id',
                                               'integration_id', 'Integrations')
    variant_integrations_data = fields.Char('Integrations data')
    brand_ids = fields.Many2many('product.brand', string='Brand')
    category_ids = fields.Many2many('product.category', string='Category')
    quantity = fields.Integer('Quantity')

    # TODO Publish variant in OMNA when supported
    # @api.model
    # def create(self, vals_list):
    #     omna_variant_id = ''
    #     omna_template_id = ''
    #     if not self._context.get('synchronizing'):
    #         if vals_list['product_tmpl_id']:
    #             template_id = self.env['product.template'].browse(vals_list['product_tmpl_id'])
    #             omna_template_id = template_id.omna_product_id
    #             if template_id:
    #                 data = {
    #                     'name': vals_list['name'],
    #                     'description': vals_list['description'],
    #                     'price': vals_list['lst_price'],
    #                     'sku': vals_list['default_code'],
    #                     'cost_price': vals_list['standard_price']
    #                 }
    #                 response = self.post('products/%s/variants' % template_id.omna_product_id, {'data': data})
    #                 if response.get('data').get('id'):
    #                     product = response.get('data')
    #                     product_template = self.env['product.template'].search([('omna_product_id', '=', template_id.omna_product_id)])
    #                     vals_list['product_tmpl_id'] = product_template.id
    #                     vals_list['omna_variant_id'] = product.get('id')
    #                     omna_variant_id = vals_list['omna_variant_id']
    #                     integrations = product_template.external_id_integration_ids.mapped('integration_id')
    #                     data_external = []
    #                     for integration in product.get('integrations'):
    #                         new_external = self.env['omna.variant.integration.external.id'].create(
    #                             {'integration_id': integration.get('id'),
    #                              'id_external': integration.get('variant').get('remote_variant_id')})
    #                         data_external.append(new_external.id)
    #                     vals_list['external_id_integration_ids'] = [(6, 0, data_external)]
    #                     p = super(ProductProduct, self).create(vals_list)
    #                     data2 = {
    #                         'integration_ids': integrations,
    #                     }
    #                     result = self.put('products/%s/variants/%s' %(omna_template_id, omna_variant_id) , {'data':data2})
    #                     self.env.user.notify_channel('warning', _(
    #                         'The task to export the order have been created, please go to "System\Tasks" to check out the task status.'),
    #                                                  _("Information"), True)
    #                     return p
    #
    #                 else:
    #                     raise exceptions.AccessError("Error trying to push product to Omna's API.")
    #     else:
    #         return super(ProductProduct, self).create(vals_list)

    def write(self, vals):
        if not self._context.get('synchronizing'):
            for record in self:
                if len(set(['name', 'price', 'default_code', 'cost_price']).intersection(vals)):

                    data = {
                        'price': vals['lst_price'] if 'lst_price' in vals else record.lst_price,
                        'sku': vals['default_code'] if 'default_code' in vals else record.default_code,
                        'quantity': vals['quantity'] if 'quantity' in vals else record.quantity,
                    }
                    # TODO Send image as data url to OMNA when supported
                    # if 'image' in vals:
                    #     data['images'] = [image_data_uri(str(vals['image']).encode('utf-8'))]
                    response = self.post('products/%s/variants/%s' % (self.omna_product_id, self.omna_variant_id),
                                         {'data': data})
                    if not response.get('data').get('id'):
                        raise exceptions.AccessError(_("Error trying to update product variant in Omna's API."))

                # TODO Send image as data url to OMNA when supported
                # if 'variant_integrations_data' in vals:
                #     old_data = json.loads(record.variant_integrations_data)
                #     new_data = json.loads(vals['variant_integrations_data'])
                #     if old_data != new_data:
                #         for integration in old_data:
                #             integration_new_data = False
                #             for integration_new in new_data:
                #                 if integration_new['id'] == integration['id']:
                #                     integration_new_data = integration_new
                #                     break
                #             if integration_new_data and integration_new_data != integration:
                #                 integration_data = {'properties': []}
                #                 for field in integration_new_data['variant']['properties']:
                #                     integration_data['properties'].append({'id': field['id'], 'value': field['value']})
                #
                #                 response = self.post(
                #                     'integrations/%s/products/%s' % (integration['id'], integration['variant']['remote_product_id']),
                #                     {'data': integration_data})
                #                 if not response.get('data').get('id'):
                #                     raise exceptions.AccessError(
                #                         _("Error trying to update products in Omna's API."))

            return super(ProductProduct, self).write(vals)
        else:
            return super(ProductProduct, self).write(vals)

    def unlink(self):
        self.check_access_rights('unlink')
        self.check_access_rule('unlink')
        for rec in self:
            integrations = [integration.integration_ids.integration_id for integration in rec.integration_ids]
            # integrations = [integration.integration_id for integration in rec.variant_integration_ids]
            data = {
                "integration_ids": integrations,
                "delete_from_integration": True,
                "delete_from_omna": True
            }
            response = rec.delete('products/%s/variants/%s' % (rec.omna_product_id, rec.omna_variant_id),
                                  {'data': data})
        return super(ProductProduct, self).unlink()



    def launch_wizard_link(self):
        view_id = self.env.ref('omna.view_link_variant_wizard').id
        context = dict(
            self.env.context,
            # integration_id=self.integration_ids.id,
            # integration_product_id=self.id,
        )

        return {
            'name': 'Link Product Variant with Integration',
            'type': 'ir.actions.act_window',
            'view_mode': 'form',
            'res_model': 'link.variant.wizard',
            'view_id': view_id,
            'views': [(view_id, 'form')],
            'target': 'new',
            'context': context,
        }



    def launch_wizard_properties_list(self):
        view_id = self.env.ref('omna.view_properties_list_variant_wizard').id
        context = dict(
            self.env.context,
            # integration_id=self.integration_ids.id,
            default_product_product_id=self.id,
        )

        return {
            'name': 'Property List By Integrations',
            'type': 'ir.actions.act_window',
            'view_mode': 'form',
            'res_model': 'properties.list.variant.wizard',
            'view_id': view_id,
            'views': [(view_id, 'form')],
            'target': 'new',
            'context': context,
        }


class SaleOrder(models.Model):
    _name = 'sale.order'
    _inherit = ['sale.order', 'omna.api']

    @api.model
    def _current_tenant(self):
        current_tenant = self.env['omna.tenant'].search([('id', '=', self.env.user.context_omna_current_tenant.id)],
                                                        limit=1)
        if current_tenant:
            return current_tenant.id
        else:
            return None

    omna_tenant_id = fields.Many2one('omna.tenant', 'Tenant', default=_current_tenant)
    omna_id = fields.Char("OMNA Order ID", index=True)
    integration_id = fields.Many2one('omna.integration', 'OMNA Integration')
    integration_name = fields.Char(string="OMNA Integration",
                                         related='integration_id.name')
    doc_type = fields.One2many('omna.doc.type', 'sale_order', string='Doc type')
    doc_omna = fields.One2many('omna.sale.doc', 'sale_order_doc', string='Omna doc')

    def action_cancel(self):
        orders = self.filtered(lambda order: not order.origin == 'OMNA')
        if orders:
            orders.write({'state': 'cancel'})

        for order in self.filtered(lambda order: order.origin == 'OMNA'):
            response = self.delete('orders/%s' % order.omna_id)
            if response:
                order.write({'state': 'cancel'})

        return True

    def action_cancel_from_integration(self):
        for order in self.filtered(lambda x: x.origin == 'OMNA'):
            response = self.delete('integrations/%s/orders/%s' %
                                   (order.integration_id.integration_id, order.name))
            if response:
                # order.action_cancel()
                self.env.user.notify_channel('warning', _(
                    'The task to cancel the order from the integration have been created, please '
                    'go to "System\Tasks" to check out the task status.'),
                                             _("Information"), True)
                order.write({'state': 'cancel'})

    def retrieve_order(self):
        try:
            orders = []
            for order in self:
                # https://cenit.io/app/ecapi-v1/orders/{order_id}
                response = self.get(
                    'orders/%s' % order.omna_id, {})
                data = response.get('data')
                orders.append(data)
                self.env['omna.order.mixin'].sync_orders(orders)


        except Exception as e:
            _logger.error(e)
            raise exceptions.AccessError(e)


class OmnaOrderLine(models.Model):
    _inherit = 'sale.order.line'

    omna_id = fields.Char("OMNA OrderLine ID", index=True)

class OmnaSaleDoc(models.Model):
    _name = 'omna.sale.doc'
    _inherit = ['omna.api']

    file = fields.Many2many('ir.attachment', string='Files')
    mime_type = fields.Char("text/html")
    title = fields.Char("Title")
    document_type = fields.Many2one('omna.doc.type', string='Type document')
    sale_order_doc = fields.Many2one('sale.order', string='Order')
    omna_doc_id = fields.Char("Document identifier in OMNA", index=True)

class OmnaDocType(models.Model):
    _name = 'omna.doc.type'
    _inherit = ['omna.api']
    _rec_name = "type"

    type = fields.Char("Document type")
    title =fields.Char("Title document type")
    omna_doc_type_id = fields.Char("Document type identifier in OMNA", index=True)
    sale_order = fields.Many2one('sale.order', string='Order')


class OmnaFilters(models.Model):
    _name = 'omna.filters'
    _rec_name = 'title'

    name = fields.Char("Name")
    title = fields.Char("Title")
    type = fields.Char("Type")


class OmnaTask(models.Model):
    _name = 'omna.task'
    _inherit = 'omna.api'
    _rec_name = 'description'

    status = fields.Selection(
        [('pending', 'Pending'), ('running', 'Running'), ('completed', 'Completed'), ('failed', 'Failed'),
         ('retrying', 'Retrying')], 'Status',
        required=True)
    description = fields.Text('Description', required=True)
    progress = fields.Float('Progress', required=True)
    task_created_at = fields.Datetime('Created At')
    task_updated_at = fields.Datetime('Updated At')
    task_execution_ids = fields.One2many('omna.task.execution', 'task_id', 'Executions')
    task_notification_ids = fields.One2many('omna.task.notification', 'task_id', 'Notifications')

    def read(self, fields_read=None, load='_classic_read'):
        result = []
        tzinfos = {
            'PST': -8 * 3600,
            'PDT': -7 * 3600,
        }
        for task_id in self.ids:
            task = self.get('tasks/%s' % omna_id2real_id(task_id), {})
            data = task.get('data')
            res = {
                'id': task_id,
                'status': data.get('status'),
                'description': data.get('description'),
                'progress': float(data.get('progress')),
                'task_created_at': fields.Datetime.to_string(
                    dateutil.parser.parse(data.get('created_at'), tzinfos=tzinfos).astimezone(pytz.utc)) if data.get(
                    'created_at') else None,
                'task_updated_at': fields.Datetime.to_string(
                    dateutil.parser.parse(data.get('updated_at'), tzinfos=tzinfos).astimezone(pytz.utc)) if data.get(
                    'updated_at') else None,
                'task_execution_ids': [],
                'task_notification_ids': []
            }
            for execution in data.get('executions', []):
                res['task_execution_ids'].append((0, 0, {
                    'status': execution.get('status'),
                    'exec_started_at': fields.Datetime.to_string(
                        dateutil.parser.parse(execution.get('started_at'), tzinfos=tzinfos).astimezone(
                            pytz.utc)) if execution.get('started_at') else None,
                    'exec_completed_at': fields.Datetime.to_string(
                        dateutil.parser.parse(execution.get('completed_at'), tzinfos=tzinfos).astimezone(
                            pytz.utc)) if execution.get('completed_at') else None,
                }))
            for notification in data.get('notifications', []):
                res['task_notification_ids'].append((0, 0, {
                    'status': notification.get('status'),
                    'message': notification.get('message')
                }))
            result.append(res)

        return result

    @api.model
    def _search(self, args, offset=0, limit=None, order=None, count=False, access_rights_uid=None):
        params = {}
        for term in args:
            if term[0] == 'description':
                params['term'] = term[2]
            if term[0] == 'status':
                params['status'] = term[2]

        if count:
            tasks = self.get('tasks', params)
            return int(tasks.get('pagination').get('total'))
        else:
            params['limit'] = limit
            params['offset'] = offset
            tasks = self.get('tasks', params)
            task_ids = self.browse([task.get('id') for task in tasks.get('data')])
            return task_ids.ids

    @api.model
    def search_read(self, domain=None, fields=None, offset=0, limit=None, order=None):
        self.check_access_rights('read')
        fields = self.check_field_access_rights('read', fields)
        result = []
        tzinfos = {
            'PST': -8 * 3600,
            'PDT': -7 * 3600,
        }
        params = {
            'limit': limit,
            'offset': offset,
        }
        for term in domain:
            if term[0] == 'description':
                params['term'] = term[2]
            if term[0] == 'status':
                params['status'] = term[2]

        tasks = self.get('tasks', params)
        for task in tasks.get('data'):
            res = {
                'id': '1-' + task.get('id'),  # amazing hack needed to open records with virtual ids
                'status': task.get('status'),
                'description': task.get('description'),
                'progress': float(task.get('progress')),
                'task_created_at': odoo.fields.Datetime.to_string(
                    dateutil.parser.parse(task.get('created_at'), tzinfos=tzinfos).astimezone(pytz.utc)),
                'task_updated_at': odoo.fields.Datetime.to_string(
                    dateutil.parser.parse(task.get('updated_at'), tzinfos=tzinfos).astimezone(pytz.utc)),
            }
            result.append(res)

        return result

    def retry(self):
        self.ensure_one()
        response = self.get('/tasks/%s/retry' % omna_id2real_id(self.id))
        return True

    def unlink(self):
        self.check_access_rights('unlink')
        self.check_access_rule('unlink')
        for rec in self:
            response = rec.delete('tasks/%s' % omna_id2real_id(rec.id))
        return True


class OmnaTaskExecution(models.Model):
    _name = 'omna.task.execution'

    status = fields.Selection(
        [('pending', 'Pending'), ('running', 'Running'), ('completed', 'Completed'), ('failed', 'Failed')], 'Status',
        required=True)
    exec_started_at = fields.Datetime('Started At')
    exec_completed_at = fields.Datetime('Completed At')
    task_id = fields.Many2one('omna.task', string='Task')


class OmnaTaskNotification(models.Model):
    _name = 'omna.task.notification'

    type = fields.Selection(
        [('info', 'Info'), ('error', 'Error'), ('warning', 'Warning')], 'Type', required=True)
    message = fields.Char('Message')
    task_id = fields.Many2one('omna.task', string='Task')


class OmnaCollection(models.Model):
    _name = 'omna.collection'
    _inherit = 'omna.api'

    @api.model
    def _current_tenant(self):
        current_tenant = self.env['omna.tenant'].search([('id', '=', self.env.user.context_omna_current_tenant.id)],
                                                        limit=1)
        if current_tenant:
            return current_tenant.id
        else:
            return None

    omna_tenant_id = fields.Many2one('omna.tenant', 'Tenant', required=True, default=_current_tenant)
    name = fields.Char('Name', required=True, readonly=True)
    title = fields.Char('Title', required=True, readonly=True)
    omna_id = fields.Char('OMNA Collection id', readonly=True)
    shared_version = fields.Char('Shared Version', readonly=True)
    summary = fields.Text('Summary', readonly=True)
    state = fields.Selection([('not_installed', 'Not Installed'), ('outdated', 'Outdated'), ('installed', 'Installed')],
                             'State', readonly=True)
    updated_at = fields.Datetime('Updated At', readonly=True)
    installed_at = fields.Datetime('Installed At', readonly=True)

    def install_collection(self):
        self.ensure_one()
        self.patch('available/integrations/%s' % self.omna_id, {})
        self.env.user.notify_channel('warning', _(
            'The task to install the collection have been created, please go to "System\Tasks" to check out the task status.'),
                                     _("Information"), True)
        return {'type': 'ir.actions.act_window_close'}

    def uninstall_collection(self):
        self.ensure_one()
        self.delete('available/integrations/%s' % self.omna_id, {})
        self.env.user.notify_channel('warning', _(
            'The task to uninstall the collection have been created, please go to "System\Tasks" to check out the task status.'),
                                     _("Information"), True)
        return {'type': 'ir.actions.act_window_close'}


class OmnaIntegrationChannel(models.Model):
    _name = 'omna.integration_channel'
    _inherit = 'omna.api'

    name = fields.Char('Name', required=True)
    title = fields.Char('Title', required=True)
    group = fields.Char('Group', required=True)
    logo = fields.Char('Logo src', compute='_compute_logo')

    @api.depends('group')
    def _compute_logo(self):
        for record in self:
            record.logo = self._get_logo(record.group)

    @api.model
    def _get_logo(self, group):
        if group == 'Lazada':
            logo = '/omna/static/src/img/lazada_logo.png'
        elif group == 'Qoo10':
            logo = '/omna/static/src/img/qoo10_logo.png'
        elif group == 'Shopee':
            logo = '/omna/static/src/img/shopee_logo.png'
        elif group == 'Shopify':
            logo = '/omna/static/src/img/shopify_logo.png'
        elif group == 'MercadoLibre':
            logo = '/omna/static/src/img/mercadolibre_logo.png'
        else:
            logo = '/omna/static/src/img/marketplace_placeholder.jpg'
        return logo

    @api.model
    def search_read(self, domain=None, fields=None, offset=0, limit=None, order=None):
        self.check_access_rights('read')
        fields = self.check_field_access_rights('read', fields)
        result = []
        channels = self.get('available/integrations/channels', {})
        for channel in channels.get('data'):
            res = {
                'id': '1-' + channel.get('name'),  # amazing hack needed to open records with virtual ids
                'name': channel.get('name'),
                'title': channel.get('title'),
                'group': channel.get('group'),
                'logo': self._get_logo(channel.get('group'))
            }
            result.append(res)

        return result

    def add_integration(self):
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'omna.integration',
            'view_mode': 'form',
            'target': 'current',
            'flags': {'form': {'action_buttons': True, 'options': {'mode': 'edit'}}}
        }


class ProductCategory(models.Model):
    _name = 'product.category'
    _inherit = ['product.category', 'omna.api']

    @api.model
    def _current_tenant(self):
        current_tenant = self.env['omna.tenant'].search([('id', '=', self.env.user.context_omna_current_tenant.id)],
                                                        limit=1)
        if current_tenant:
            return current_tenant.id
        else:
            return None

    omna_tenant_id = fields.Many2one('omna.tenant', 'Tenant', default=_current_tenant)
    omna_category_id = fields.Char("Category identifier in OMNA", index=True)
    integration_id = fields.Many2one('omna.integration', 'OMNA Integration')
    integration_category_name = fields.Char(related='integration_id.name', readonly=False, store=True)
    product_count_cat = fields.Integer('# Products', compute='_compute_product_count_cat')
    product_category_ids = fields.Many2many(
        comodel_name='product.template',
        string='Product')

    def _compute_product_count_cat(self):
        for category in self:
            category.product_count_cat = self.env['product.template'].search_count(
                [('category_ids', 'in', category.id)])

    def view_product_category(self):
        self.ensure_one()
        return {
            'name': 'Product',
            'type': 'ir.actions.act_window',
            'res_model': 'product.template',
            'view_mode': 'kanban,tree,form,activity',
            'domain': [('id', 'in', self.product_category_ids.ids)]

        }


class ProductBrand(models.Model):
    _name = 'product.brand'
    _description = 'Brand of the product'
    _order = 'name asc'

    @api.model
    def _current_tenant(self):
        current_tenant = self.env['omna.tenant'].search([('id', '=', self.env.user.context_omna_current_tenant.id)],
                                                        limit=1)
        if current_tenant:
            return current_tenant.id
        else:
            return None

    omna_tenant_id = fields.Many2one('omna.tenant', 'Tenant', default=_current_tenant)
    name = fields.Char('Brand', required=False)
    omna_brand_id = fields.Char("Brand identifier in OMNA", index=True)
    integration_id = fields.Many2one('omna.integration', 'OMNA Integration')
    integration_brand_name = fields.Char(related='integration_id.name', readonly=False)
    product_count_br = fields.Integer('# Products', compute='_compute_product_count_br')
    product_brand_ids = fields.Many2many(
        comodel_name='product.template',
        string='Product')

    def _compute_product_count_br(self):
        for brand in self:
            brand.product_count_br = self.env['product.template'].search_count(
                [('brand_ids', 'in', brand.id)])

    def view_product_brand(self):
        self.ensure_one()
        return {
            'name': 'Product',
            'type': 'ir.actions.act_window',
            'res_model': 'product.template',
            'view_mode': 'kanban,tree,form,activity',
            'domain': [('id', 'in', self.product_brand_ids.ids)]

        }

class ProductAttributeValue(models.Model):
    _inherit = "product.attribute.value"

    name = fields.Char(string='Value', required=False, translate=True)