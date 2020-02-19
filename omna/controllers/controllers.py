# -*- coding: utf-8 -*-
from odoo import http, exceptions
from odoo.http import request
import odoo
import logging
import json
import werkzeug
import requests
import dateutil.parser
import pytz

_logger = logging.getLogger(__name__)


class Omna(http.Controller):
    @http.route('/omna/sign_in/', type='http', auth='user')
    def sing_in(self, code, **kw):
        request.env.user.context_omna_get_access_token_code = str(code)
        action = request.env.ref('omna.action_omna_orders').read()[0]
        return werkzeug.utils.redirect('/web#action=%s' % action['id'] or '', 301)

    @http.route('/omna/get_access_token/', type='json', auth='user', methods=['POST'], csrf=False)
    def get_access_token(self, default_tenant=None, **kw):
        request.env.user.context_omna_get_access_token_code = None
        if default_tenant and default_tenant.get('id', False):
            tenant = request.env["omna.tenant"].search([('omna_tenant_id', '=', default_tenant.get('id'))])
            tzinfos = {
                'PST': -8 * 3600,
                'PDT': -7 * 3600,
            }
            if tenant:
                tenant.write({
                    'name': default_tenant.get('name'),
                    'token': default_tenant.get('token'),
                    'secret': default_tenant.get('secret'),
                    'is_ready_to_omna': default_tenant.get('is_ready_to_omna'),
                    'deactivation': odoo.fields.Datetime.to_string(
                        dateutil.parser.parse(default_tenant.get('deactivation'), tzinfos=tzinfos).astimezone(pytz.utc)),
                })
                tenant._switch()
            else:
                created_tenant = request.env["omna.tenant"].with_context({'synchronizing': True}).create({
                    'omna_tenant_id': default_tenant.get('id'),
                    'name': default_tenant.get('name'),
                    'token': default_tenant.get('token'),
                    'secret': default_tenant.get('secret'),
                    'is_ready_to_omna': default_tenant.get('is_ready_to_omna'),
                    'deactivation': odoo.fields.Datetime.to_string(
                        dateutil.parser.parse(default_tenant.get('deactivation'), tzinfos=tzinfos).astimezone(pytz.utc)),
                    # 'current': True
                })
                request.env.user.context_omna_current_tenant = created_tenant
            return True

        return False

    @http.route('/omna/integrations/authorize/<string:integration_id>', type='http', auth='user', methods=['GET'])
    def authorize_integration(self, integration_id, **kw):
        request.env.user.context_omna_get_access_token_code = None
        integration = request.env['omna.integration'].search(['integration_id', '=', integration_id], limit=1)
        if integration:
            integration.write({'authorized': True})
            return {
                'type': 'ir.actions.client',
                'tag': 'reload',
                'params': {'menu_id': self.env.ref('omna.menu_omna_integration').id},
            }
        else:
            raise exceptions.AccessError(_("Invalid integration id."))
