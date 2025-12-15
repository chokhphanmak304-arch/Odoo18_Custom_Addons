# -*- coding: utf-8 -*-
{
    'name': 'Account Payment Method Extended',
    'version': '18.0.1.0.0',
    'category': 'Account',
    'summary': 'Extend Account Payment Method with additional fields',
    'description': """Extend Account Payment Method""",
    'author': 'Perfect Blending',
    'website': 'https://www.perfectblending.com',
    'license': 'LGPL-3',
    'depends': ['account'],
    'data': [
        'views/payment_method_view.xml',
    ],
    'installable': True,
    'auto_install': False,
}
