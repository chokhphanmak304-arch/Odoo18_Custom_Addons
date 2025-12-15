from odoo import fields, models


class CrmLead(models.Model):
    _inherit = 'crm.lead'

    customer_from_channel = fields.Selection(
        selection=[
            ('not_known', 'Not Known'),
            ('facebook', 'Facebook'),
            ('tiktok', 'Tiktok'),
            ('line', 'Line'),
            ('bci', 'BCI'),
            ('walk_in', 'Walk In'),
            ('website_google', 'Website/Google'),
        ],
        string='ลูกค้ามาจากช่องทาง'
    )