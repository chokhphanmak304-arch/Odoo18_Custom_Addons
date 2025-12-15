from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError


class DateChequeDone(models.TransientModel):
    _name = "date.cheque.done"
    _description = "Date Cheque Done Wizard"

    date_done = fields.Date('Date Receipt', default=fields.Datetime.now, required=True)

    def action_done_cheque(self):
        cheques = self.env['account.cheque'].browse(self._context.get('active_ids', []))
        for cq in cheques:
            cq.date_receipt = self.date_done
        return True
