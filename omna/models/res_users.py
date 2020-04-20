# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, tools, SUPERUSER_ID, _
import logging


_logger = logging.getLogger(__name__)


class ResUsers(models.Model):
    _inherit = 'res.users'

    def _compute_omna_manager(self):
        self.context_omna_manager = self.has_group('omna.group_omna_manager')

    def _default_current_tenant(self):
        return self.env['omna.tenant'].search([], limit=1).id

    def _default_omna_urls(self):
        url = self.env["ir.config_parameter"].sudo().get_param("omna_odoo.cenit_url")
        self.context_omna_get_access_token_url = '%s/%s' % (url, 'get_access_token') if url else None
        self.context_omna_base_url = url if url else None

    context_omna_current_tenant = fields.Many2one('omna.tenant', string='Omna Current Tenant', default=_default_current_tenant)
    context_omna_manager = fields.Boolean('Omna Manager', compute='_compute_omna_manager')
    context_omna_get_access_token_code = fields.Char('Code to retrieve access token from Omna')
    context_omna_get_access_token_url = fields.Char('Url to retrieve access token from Omna', compute='_default_omna_urls')
    context_omna_base_url = fields.Char('Omna API base url', compute='_default_omna_urls')
