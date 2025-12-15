from odoo import models, fields, api

from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta

class CrmLead(models.Model):
    _inherit = 'crm.lead'

    customer_status = fields.Selection(
        selection=[
            ('old', 'ลูกค้าเก่า'),
            ('new', 'ลูกค้าใหม่'),
        ],
        string='ประเภทลูกค้า',
        default='old',
        required=True
    )

    position_owner = fields.Selection(
        selection=[
            ('sale_support', 'Sale Support'),
            ('sale_project', 'Sale Project'),
            ('telesale', 'Telesale'),
        ],
        string='ตำแหน่งผู้รับผิดชอบ',
        required=True,
        help='บังคับกรอก: เลือกบทบาทที่ถือเคสนี้'
    )

    source_user_id = fields.Many2one(
        'res.users',
        string='แหล่งที่มา',
        default=lambda self: self.env.user,  # ดึงผู้ล็อกอินตอนสร้าง
        readonly=True
    )

    net_amount = fields.Monetary(
        string='ยอดสุทธิ',
        currency_field='company_currency',  # ใช้สกุลเงินบริษัทตามมาตรฐาน CRM
        required=True,
        default=0.0,
        help='กรอกยอดสุทธิที่ต้องการบันทึก (ไม่คำนวณอัตโนมัติ)'
    )

    # ===== แก้ไขส่วนนี้ =====
    total_amount_customer = fields.Monetary(
        string='ยอดสะสมของลูกค้า',
        currency_field='company_currency',
        compute='_compute_total_amount_customer',
        store=False,
        readonly=True,
        help='ยอดรวมจาก Sale Orders ทั้งหมดของลูกค้านี้'
    )

    partner_sale_count = fields.Integer(
        string='จำนวนบิลขาย',
        compute='_compute_total_amount_customer',
        store=False,
        readonly=True,
        help='จำนวนใบสั่งขายทั้งหมดของลูกค้า'
    )

    # เพิ่ม field สำหรับแสดงรายละเอียดแต่ละบิล
    sale_order_details = fields.Html(
        string='รายละเอียดบิลขาย',
        compute='_compute_total_amount_customer',
        store=False,
        readonly=True,
        help='แสดงเลขที่บิลและยอดเงินแต่ละบิล'
    )

    @api.depends('partner_id')
    def _compute_total_amount_customer(self):
        """
        คำนวณยอดรวมของลูกค้าจาก Sale Orders
        และสร้างตารางแสดงรายละเอียดแต่ละบิล
        """
        for record in self:
            if record.partner_id:
                # ===== แก้ส่วนนี้ - เพิ่ม filter เฉพาะ SO =====
                # ค้นหา Sale Orders ทั้งหมดของลูกค้านี้
                # เฉพาะบิลที่ยืนยันแล้ว (state = sale หรือ done)
                # และเฉพาะเลขที่บิลที่ขึ้นต้นด้วย 'SO' (ไม่เอา 'QT')
                sale_orders = self.env['sale.order'].search([
                    ('partner_id', '=', record.partner_id.id),
                    ('state', 'in', ['sale', 'done']),  # เฉพาะบิลที่ยืนยันแล้ว
                    ('name', '=like', 'SO%')  # เฉพาะเลขบิลที่ขึ้นต้นด้วย SO
                ], order='date_order desc')  # เรียงตามวันที่ล่าสุด
                # ===== จบส่วนที่แก้ =====

                # คำนวณยอดรวม
                record.total_amount_customer = sum(sale_orders.mapped('amount_total'))
                record.partner_sale_count = len(sale_orders)

                # สร้างตาราง HTML แสดงรายละเอียดแต่ละบิล
                if sale_orders:
                    html_content = """
                       <div style="margin-top: 10px;">
                           <table class="table table-sm table-striped" style="width: 100%; border: 1px solid #ddd;">
                               <thead style="background-color: #875a7b; color: white;">
                                   <tr>
                                       <th style="padding: 8px; text-align: left;">เลขที่บิล</th>
                                       <th style="padding: 8px; text-align: left;">วันที่</th>
                                       <th style="padding: 8px; text-align: left;">สถานะ</th>
                                       <th style="padding: 8px; text-align: right;">ยอดเงิน</th>
                                   </tr>
                               </thead>
                               <tbody>
                       """

                    # วนลูปแสดงแต่ละบิล
                    for order in sale_orders:
                        # แปลง state เป็นภาษาไทย
                        state_label = {
                            'sale': 'ยืนยันแล้ว',
                            'done': 'เสร็จสิ้น',
                        }.get(order.state, order.state)

                        # จัดรูปแบบเงิน
                        amount_formatted = "{:,.2f}".format(order.amount_total)
                        currency = order.currency_id.symbol or 'THB'

                        # แปลงวันที่เป็นรูปแบบไทย
                        date_str = order.date_order.strftime('%d/%m/%Y') if order.date_order else '-'

                        html_content += f"""
                               <tr>
                                   <td style="padding: 6px;">{order.name}</td>
                                   <td style="padding: 6px;">{date_str}</td>
                                   <td style="padding: 6px;">{state_label}</td>
                                   <td style="padding: 6px; text-align: right; font-weight: bold;">
                                       {amount_formatted} {currency}
                                   </td>
                               </tr>
                           """

                    # ปิดตารางและแสดงยอดรวม
                    total_formatted = "{:,.2f}".format(record.total_amount_customer)
                    html_content += f"""
                               </tbody>
                               <tfoot style="background-color: #f5f5f5; font-weight: bold;">
                                   <tr>
                                       <td colspan="3" style="padding: 8px; text-align: right;">ยอดรวมทั้งหมด:</td>
                                       <td style="padding: 8px; text-align: right; color: #875a7b; font-size: 16px;">
                                           {total_formatted} {currency}
                                       </td>
                                   </tr>
                               </tfoot>
                           </table>
                       </div>
                       """
                    record.sale_order_details = html_content
                else:
                    record.sale_order_details = '<p style="color: #999;">ไม่พบบิลขายของลูกค้านี้</p>'
            else:
                # ถ้าไม่มี partner ให้เป็น 0
                record.total_amount_customer = 0.0
                record.partner_sale_count = 0
                record.sale_order_details = '<p style="color: #999;">กรุณาเลือกลูกค้า</p>'

    # ===== จบส่วนที่แก้ไข =====

    @api.model
    def create(self, vals):
        # กันกรณี dev อื่นยัดค่าแปลก ๆ ข้าม view
        if not vals.get('source_user_id'):
            vals['source_user_id'] = self.env.user.id
        return super().create(vals)

    def write(self, vals):
        # ล็อกไม่ให้แก้แหล่งที่มา (หากมีพยายามแก้ -> ตัดทิ้ง)
        if 'source_user_id' in vals:
            vals.pop('source_user_id', None)
        return super().write(vals)

    @api.model
    def search(self, args, offset=0, limit=None, order=None, count=False):
        """Override search เพื่อจัดการ filter เดือนนี้ และเดือนที่แล้ว"""
        ctx = self.env.context

        # ถ้า context มี filter_this_month
        if ctx.get('filter_this_month'):
            today = datetime.now()
            # วันแรกของเดือนปัจจุบัน
            start_month = today.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            # เพิ่ม domain condition
            args = args + [('create_date', '>=', start_month)]

        # ถ้า context มี filter_last_month
        if ctx.get('filter_last_month'):
            today = datetime.now()
            # วันแรกของเดือนปัจจุบัน
            start_this_month = today.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            # วันแรกของเดือนที่แล้ว
            start_last_month = start_this_month - relativedelta(months=1)
            # เพิ่ม domain conditions
            args = args + [
                ('create_date', '>=', start_last_month),
                ('create_date', '<', start_this_month)
            ]

        return super(CrmLead, self).search(args, offset, limit, order, count)

        # Field สำหรับนับจำนวนใบแจ้งหนี้ค้างชำระ

    overdue_invoice_count = fields.Integer(
        string='จำนวนบิลค้างชำระ',
        compute='_compute_overdue_invoices',
        store=False,
        help='จำนวนใบแจ้งหนี้ที่ยังไม่ได้ชำระเงิน'
    )

    # Field สำหรับยอดเงินค้างชำระทั้งหมด
    overdue_amount_total = fields.Monetary(
        string='ยอดเงินค้างชำระ',
        currency_field='company_currency',
        compute='_compute_overdue_invoices',
        store=False,
        help='ยอดรวมเงินที่ยังค้างชำระ'
    )

    # Field HTML สำหรับแสดงตารางใบแจ้งหนี้ค้างชำระ
    overdue_invoice_details = fields.Html(
        string='รายละเอียดบิลค้างชำระ',
        compute='_compute_overdue_invoices',
        store=False,
        help='แสดงตารางรายละเอียดใบแจ้งหนี้ที่ค้างชำระ'
    )

    @api.depends('partner_id')
    def _compute_overdue_invoices(self):
        """
        คำนวณและแสดงใบแจ้งหนี้ค้างชำระของลูกค้า
        """
        for record in self:
            if record.partner_id:
                # ค้นหาใบแจ้งหนี้ที่ค้างชำระ
                invoices = self.env['account.move'].search([
                    ('partner_id', '=', record.partner_id.id),
                    ('move_type', '=', 'out_invoice'),
                    ('state', '!=', 'cancel'),
                    ('payment_state', '=', 'not_paid'),
                ], order='invoice_date desc')

                # นับจำนวนและคำนวณยอดรวม
                record.overdue_invoice_count = len(invoices)
                record.overdue_amount_total = sum(invoices.mapped('amount_residual_signed'))

                # สร้างตาราง HTML
                if invoices:
                    # คำนวณค่าก่อน
                    invoice_count = len(invoices)
                    total_amount = record.overdue_amount_total
                    currency = invoices[0].currency_id.symbol if invoices else '฿'

                    # ===== แก้ไขส่วนนี้ - เปลี่ยน {} เป็น {{}} ใน CSS =====
                    html_content = f"""
                        <style>
                            .overdue-table {{
                                width: 100%;
                                border-collapse: collapse;
                                margin-top: 10px;
                                font-size: 13px;
                            }}
                            .overdue-table th {{
                                background-color: #dc3545;
                                color: white;
                                padding: 10px;
                                text-align: left;
                                font-weight: bold;
                            }}
                            .overdue-table td {{
                                padding: 8px;
                                border-bottom: 1px solid #ddd;
                            }}
                            .overdue-table tr:hover {{
                                background-color: #f8f9fa;
                            }}
                            .overdue-table tfoot td {{
                                background-color: #fff3cd;
                                font-weight: bold;
                                padding: 10px;
                                border-top: 2px solid #dc3545;
                            }}
                            .amount-col {{
                                text-align: right;
                                font-weight: bold;
                                color: #dc3545;
                            }}
                            .overdue-badge {{
                                background-color: #dc3545;
                                color: white;
                                padding: 3px 8px;
                                border-radius: 3px;
                                font-size: 11px;
                            }}
                            .partial-badge {{
                                background-color: #ffc107;
                                color: #000;
                                padding: 3px 8px;
                                border-radius: 3px;
                                font-size: 11px;
                            }}
                        </style>
                        <div style="margin: 10px;">
                            <div style="background-color: #f8d7da; padding: 15px; border-radius: 5px; margin-bottom: 15px; border-left: 4px solid #dc3545;">
                                <h4 style="margin: 0 0 10px 0; color: #721c24;">
                                    ⚠️ มีใบแจ้งหนี้ค้างชำระ {invoice_count} รายการ
                                </h4>
                                <p style="margin: 0; color: #721c24;">
                                    ยอดเงินค้างชำระทั้งหมด: <strong>{total_amount:,.2f} {currency}</strong>
                                </p>
                            </div>

                            <table class="overdue-table">
                                <thead>
                                    <tr>
                                        <th style="width: 15%;">เลขที่ใบแจ้งหนี้</th>
                                        <th style="width: 12%;">วันที่ออกบิล</th>
                                        <th style="width: 12%;">วันครบกำหนด</th>
                                        <th style="width: 15%;">สาขา</th>
                                        <th style="width: 13%;">สถานะ</th>
                                        <th style="width: 18%;">เหตุผล</th>
                                        <th style="width: 15%; text-align: right;">ยอดค้างชำระ</th>
                                    </tr>
                                </thead>
                                <tbody>
                    """
                    # ===== จบส่วนที่แก้ไข =====

                    # วนลูปแสดงแต่ละใบแจ้งหนี้
                    for invoice in invoices:
                        invoice_number = invoice.name or '-'
                        invoice_date = invoice.invoice_date.strftime('%d/%m/%Y') if invoice.invoice_date else '-'
                        invoice_due = invoice.invoice_date_due.strftime('%d/%m/%Y') if invoice.invoice_date_due else '-'

                        # ตรวจสอบว่าเกินกำหนดชำระหรือไม่
                        is_overdue = False
                        days_overdue = 0
                        overdue_indicator = ''
                        if invoice.invoice_date_due:
                            days_overdue = (fields.Date.today() - invoice.invoice_date_due).days
                            is_overdue = days_overdue > 0
                            if is_overdue:
                                overdue_indicator = f' <span style="color: #dc3545; font-size: 11px;">⏰ เกิน {days_overdue} วัน</span>'

                        # สาขา
                        branch_name = invoice.branch_id.name if invoice.branch_id else '-'

                        # สถานะการชำระเงิน
                        payment_state_dict = {
                            'not_paid': '<span class="overdue-badge">ยังไม่ชำระเงิน</span>',
                            'in_payment': '<span class="partial-badge">กำลังชำระ</span>',
                            'paid': '<span style="background-color: #28a745; color: white; padding: 3px 8px; border-radius: 3px;">ชำระแล้ว</span>',
                            'partial': '<span class="partial-badge">ชำระบางส่วน</span>',
                            'reversed': '<span style="background-color: #6c757d; color: white; padding: 3px 8px; border-radius: 3px;">ถูกกลับรายการ</span>',
                        }
                        payment_status = payment_state_dict.get(invoice.payment_state, invoice.payment_state)

                        # เหตุผล
                        reason = invoice.reason_code_id.name if invoice.reason_code_id else '-'

                        # จำนวนเงินค้างชำระ
                        amount_residual = invoice.amount_residual_signed
                        amount_formatted = "{:,.2f}".format(abs(amount_residual))
                        invoice_currency = invoice.currency_id.symbol or '฿'

                        html_content += f"""
                            <tr style="{'background-color: #fff5f5;' if is_overdue else ''}">
                                <td><strong>{invoice_number}</strong></td>
                                <td>{invoice_date}</td>
                                <td>{invoice_due}{overdue_indicator}</td>
                                <td>{branch_name}</td>
                                <td>{payment_status}</td>
                                <td>{reason}</td>
                                <td class="amount-col">{amount_formatted} {invoice_currency}</td>
                            </tr>
                        """

                    # Footer ยอดรวม
                    html_content += f"""
                                </tbody>
                                <tfoot>
                                    <tr>
                                        <td colspan="6" style="text-align: right;">
                                            <strong>ยอดรวมค้างชำระทั้งหมด:</strong>
                                        </td>
                                        <td class="amount-col" style="font-size: 16px; color: #dc3545;">
                                            {total_amount:,.2f} {currency}
                                        </td>
                                    </tr>
                                </tfoot>
                            </table>
                        </div>
                    """

                    record.overdue_invoice_details = html_content
                else:
                    # ไม่มีบิลค้างชำระ
                    record.overdue_invoice_details = """
                        <div style="text-align: center; padding: 40px; color: #28a745;">
                            <h3>✅ ไม่มีบิลค้างชำระ</h3>
                            <p style="color: #6c757d;">ลูกค้ารายนี้ชำระเงินครบถ้วนแล้ว</p>
                        </div>
                    """
            else:
                # ไม่มีลูกค้า
                record.overdue_invoice_count = 0
                record.overdue_amount_total = 0.0
                record.overdue_invoice_details = """
                    <div style="text-align: center; padding: 40px; color: #6c757d;">
                        <p>กรุณาเลือกลูกค้าก่อน</p>
                    </div>
                """

    # ===== แก้ไข method เดิม =====
    def action_check_overdue_credit(self):
        """
        เปิด popup แสดงใบแจ้งหนี้ค้างชำระ
        """
        self.ensure_one()

        if not self.partner_id:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': '⚠️ คำเตือน',
                    'message': 'กรุณาเลือกลูกค้าก่อน',
                    'type': 'warning',
                }
            }

        # เปิด popup wizard view ที่เราจะสร้าง
        return {
            'name': f'🔍 เช็คเครดิตค้างชำระ: {self.partner_id.name}',
            'type': 'ir.actions.act_window',
            'res_model': 'crm.lead',
            'res_id': self.id,
            'view_mode': 'form',
            'view_id': self.env.ref('custom_crm_customer_status.view_crm_lead_overdue_popup').id,
            'target': 'new',
            'context': dict(self.env.context),
        }
   # ===== จบส่วนที่เพิ่ม =====

