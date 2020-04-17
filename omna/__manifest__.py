# -*- coding: utf-8 -*-
{
    'name': 'OMNA Marketplace Connector',
    'version': '12.0.0.1.0',
    'category': 'Sales',
    'summary': 'Integration: Shopify, Shopee, Lazada, Qoo10, MercadoLibre, Backmarket, Shipstation',
    'description': 'Integrate global online marketplaces & web-stores with Odoo. Sync products, inventory and orders from multiple channels',
    'author': 'Cenit IO',
    'website': 'https://www.omna.io/',
    'license': 'OPL-1',
    'support': 'support@omna.io',

    # any module necessary for this one to work correctly
    'depends': ['base', 'sale_management'],

    # always loaded
    'data': [
        # security
        'security/omna_security.xml',
        'security/ir.model.access.csv',

        # views
        'views/parent.xml',
        'views/config.xml',
        'views/data.xml',
        'views/integrations.xml',
        'views/integration_channels.xml',
        'views/webhooks.xml',
        'views/tasks.xml',
        'views/flows.xml',
        'views/tenants.xml',
        'views/collections.xml',
        'views/omna_templates.xml',

        # wizard
        'wizard/omna_sync_products_view.xml',
        'wizard/omna_sync_orders_view.xml',
        'wizard/omna_sync_integrations_view.xml',
        'wizard/omna_sync_workflows_view.xml',
        'wizard/omna_action_start_workflows_view.xml',
        'wizard/omna_action_status_workflows_view.xml',
        'wizard/omna_sync_tenants_view.xml',
        'wizard/omna_sync_collections_view.xml',
        'wizard/omna_publish_product_view.xml',
        'wizard/omna_unpublish_product_view.xml',

        # initial data
        'data/dow.xml',
        'data/wom.xml',
        'data/moy.xml'

    ],
    'qweb': [
        'static/src/xml/systray.xml',
    ],
    # only loaded in demonstration mode
    'demo': [
        'demo/demo.xml',
    ],
    'images': ['static/images/banner.jpg'],
    "installable": True,
    'application': True,
    'auto_install': False,
}
