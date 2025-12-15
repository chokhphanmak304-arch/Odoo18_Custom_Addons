from odoo import models, fields, api


class AccountPaymentMethod(models.Model):
    _inherit = 'account.payment.method'

    # Extended fields for custom payment method functionality
    type = fields.Selection(
        selection=[
            ('cash', 'Cash'),
            ('cheque', 'Cheque'),
            ('bank', 'Bank'),
            ('discount', 'Discount'),
            ('ap', 'AP'),
            ('ar', 'AR'),
            ('other', 'Other')
        ],
        string='Payment Type Custom',
        default='cash'
    )
    account_id = fields.Many2one(
        'account.account',
        string="Account",
    )
    is_active = fields.Boolean(string='Active', default=True)
    company_id = fields.Many2one(
        comodel_name="res.company",
        string="Company",
        default=lambda self: self.env.company,
    )

    @api.onchange('type')
    def _onchange_type(self):
        if self.type and not self.name:
            self.name = dict(self._fields['type'].selection).get(self.type)
