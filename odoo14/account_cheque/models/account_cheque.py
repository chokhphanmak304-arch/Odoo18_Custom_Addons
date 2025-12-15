from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError


class AccountCheque(models.Model):
    _name = "account.cheque"
    _inherit = ["mail.thread", "mail.activity.mixin", "portal.mixin"]
    _description = "cheque payment and receipt"
    _order = 'date_cheque DESC'

    name = fields.Char(string="Cheque Number", required=True)
    date_cheque = fields.Date(
        string="Date Cheque", required=True, default=fields.Datetime.now
    )
    date_done = fields.Date(string="Date Cheque Transher")
    date_receipt = fields.Date(string="Date Cheque Receipt")
    cheque_type = fields.Selection(
        [
            ("outbound", "Payment Cheque"),
            ("inbound", "Receipt Cheque"),
        ],
        string="Type",
        default="inbound",
        required=True,
    )
    cheque_total = fields.Float(string="Cheque Total", digits=(24, 2), required=True)
    remark = fields.Text(string="Note")
    state = fields.Selection(
        [
            ("draft", "Draft"),
            ('assigned', 'Assigned'),
            ('reject', 'Reject'),
            ("done", "Done"),
            ("cancel", "Cancel"),
        ],
        string="Status",
        default="draft",
    )
    partner_id = fields.Many2one("res.partner", string="Partner")
    payee_id = fields.Many2one("res.partner", string="Payee Cheque")
    employee_id = fields.Many2one(
        comodel_name="hr.employee",
        ondelete='cascade',
        index=True,
        string='Receipt User'
    )
    bank_partner_id = fields.Many2one(
        "res.partner.bank", string="Bank Account Transfer"
    )
    bank_id = fields.Many2one("res.bank", string="Bank")
    move_id = fields.Many2one("account.move", string="Move Entry")
    payment_id = fields.Many2one("account.payment", string="Receipt/Payment", compute='_compute_payment_id')

    account_bank_id = fields.Many2one(
        "account.account", 
        string="Account Bank", 
        domain="[('account_type', '=', 'asset_cash')]"
    )
    journal_id = fields.Many2one(
        'account.journal',
        'Journal',
        readonly=False,
        tracking=True
    )
    payment_method_id = fields.Many2one(
        "account.payment.method", 
        string="Payment Method", 
        domain="[('type', '=', 'cheque'), ('is_active','=',True),'|',('company_id', '=', False),('company_id', '=', company_id)]",
        required=True
    )
    format_type = fields.Selection(
        string="Format Cheque",
        selection=[
            ('ac_bank', '1 - ขีดคร่อมเข้าบัญชี'),
            ('ac_payee', '2 - A/C Payee Only'),
            ('co', '3 - &CO')
        ],
        required=True,
    )
    company_id = fields.Many2one(
        'res.company', 'Company',
        store=True, readonly=True,
        default=lambda self: self.env.company
    )
    
    _sql_constraints = [
        ('name_unique', 'unique (name)', 'Cheque No. must be unique !')
    ]

    def _compute_payment_id(self):
        for cheque in self:
            payment_id = cheque.payment_id.search([('cheque_id', '=', cheque.id)], limit=1)
            payment_line_ids = self.env['account.paid.line'].search([('cheque_id', '=', cheque.id)])
            for payment_line in payment_line_ids:
                payment_id = payment_line.payment_id
            cheque.payment_id = payment_id

    @api.onchange('bank_partner_id')
    def _onchange_bank_partner_id(self):
        self.account_bank_id = self.bank_partner_id.account_bank_id.id

    def create_account_move(self):
        vals = []
        account_move = self.env["account.move"]
        if not self.account_bank_id:
            raise UserError(_("Please select Account Bank"))
        if not self.date_done:
            raise UserError(_("Please select Date Done"))
        cheque_total = self.cheque_type == 'outbound' and -self.cheque_total or self.cheque_total
        vals.append(
            [
                0,
                0,
                {
                    "account_id": self.account_bank_id.id,
                    "debit": cheque_total > 0 and abs(cheque_total) or 0,
                    "credit": cheque_total < 0 and abs(cheque_total) or 0,
                    "name": self.name,
                    "date": self.date_done,
                },
            ]
        )

        vals.append(
            [
                0,
                0,
                {
                    "account_id": self.payment_method_id.account_id.id,
                    "debit": cheque_total < 0 and abs(cheque_total) or 0,
                    "credit": cheque_total > 0 and abs(cheque_total) or 0,
                    "name": self.name,
                    "date": self.date_done,
                },
            ]
        )

        move_id = account_move.create(
            {
                "date": self.date_done,
                "journal_id": self.journal_id.id,
                "ref": self.name,
                "line_ids": vals,
            }
        )
        move_id.action_post()
        self.move_id = move_id
        return True
    
    def action_confirm(self):
        self.create_account_move()
        self.state = "done"

    def action_assigned(self):
        self.state = "assigned"

    def action_reject(self):
        self.state = 'reject'

    def action_cancel(self):
        self.move_id.button_draft()
        self.move_id.button_cancel()
        self.state = "cancel"

    def action_redraft(self):
        self.state = "draft"

    @api.onchange('partner_id')
    def onchange_method(self):
        self.payee_id = self.partner_id

    def action_cheque_done(self):
        return {
            'name': _('Done Cheque'),
            'res_model': 'date.cheque.done',
            'view_mode': 'form',
            'context': {
                'active_model': 'account.cheque',
                'active_ids': self.ids,
            },
            'target': 'new',
            'type': 'ir.actions.act_window',
        }
        
    @api.onchange('date_receipt')
    def _onchange_date_receipt(self):
        self.date_done = self.date_receipt
    

class ResPartnerBank(models.Model):
    _inherit = "res.partner.bank"

    account_bank_id = fields.Many2one("account.account", string="Account Bank")
