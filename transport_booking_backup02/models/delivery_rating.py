# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
import uuid
import logging
import json
import base64
import hmac
import hashlib
from datetime import datetime, timedelta

_logger = logging.getLogger(__name__)


class DeliveryRating(models.Model):
    _name = 'delivery.rating'
    _description = 'Customer Delivery Rating / การประเมินการขนส่งโดยลูกค้า'
    _order = 'create_date desc'
    _rec_name = 'booking_id'

    # ✅ JWT Configuration
    JWT_SECRET = 'npd-transport-rating-secret-2024'
    TOKEN_EXPIRY = 7 * 24 * 60 * 60  # 7 วัน (เปลี่ยนตัวเลข 7 เป็นจำนวนวันที่ต้องการ)
    # 14
    # วัน: TOKEN_EXPIRY = 14 * 24 * 60 * 60
    # 30
    # วัน: TOKEN_EXPIRY = 30 * 24 * 60 * 60

    # ข้อมูลการประเมิน
    booking_id = fields.Many2one('vehicle.booking', string='การจองขนส่ง', 
                                  required=True, ondelete='cascade', index=True)
    driver_id = fields.Many2one('vehicle.driver', string='พนักงานขับรถ',
                                related='booking_id.driver_id', store=True, readonly=True)
    driver_name = fields.Char('ชื่อพนักงาน', related='driver_id.name', store=True, readonly=True)
    
    # Token สำหรับ public URL
    rating_token = fields.Char('Rating Token (UUID)', default=lambda self: str(uuid.uuid4()), 
                               required=True, readonly=True, copy=False, index=True, unique=True)
    
    # ✅ JWT Token (ใหม่)
    jwt_token = fields.Char('JWT Token', readonly=True, copy=False, index=True)
    
    # คะแนนประเมิน
    rating_stars = fields.Selection([
        ('1', '⭐ แย่มาก'),
        ('2', '⭐⭐ แย่'),
        ('3', '⭐⭐⭐ ปานกลาง'),
        ('4', '⭐⭐⭐⭐ ดี'),
        ('5', '⭐⭐⭐⭐⭐ ดีมาก'),
    ], string='คะแนนประเมิน')
    
    rating_value = fields.Integer('คะแนน (1-5)', compute='_compute_rating_value', store=True)
    
    # ความคิดเห็น
    customer_comment = fields.Text('ความคิดเห็นจากลูกค้า')
    
    # วันที่
    rating_date = fields.Datetime('วันที่ประเมิน', readonly=True)
    
    # สถานะ
    state = fields.Selection([
        ('pending', 'รอการประเมิน'),
        ('done', 'ประเมินแล้ว'),
        ('expired', 'หมดอายุ'),
    ], string='สถานะ', default='pending', required=True)
    
    # ข้อมูลเพิ่มเติม
    customer_name = fields.Char('ชื่อลูกค้า', related='booking_id.partner_id.name', 
                                 store=True, readonly=True)
    pickup_location = fields.Text('สถานที่รับ', related='booking_id.pickup_location', 
                                   store=True, readonly=True)
    destination = fields.Text('ปลายทาง', related='booking_id.destination', 
                             store=True, readonly=True)
    
    # Public Link
    rating_url = fields.Char('Link ประเมิน', compute='_compute_rating_url', store=False)
    
    # SQL Constraints
    _sql_constraints = [
        ('booking_unique', 'UNIQUE(booking_id)', 
         '⚠️ การจองนี้มี Link ประเมินอยู่แล้ว! ไม่สามารถสร้างซ้ำได้'),
    ]
    
    # ========================================
    # Compute Methods
    # ========================================
    
    @api.depends('rating_stars')
    def _compute_rating_value(self):
        """แปลง rating_stars เป็นตัวเลข"""
        for record in self:
            if record.rating_stars:
                record.rating_value = int(record.rating_stars)
            else:
                record.rating_value = 0
    
    @api.depends('rating_token')
    def _compute_rating_url(self):
        """สร้าง Public URL สำหรับการประเมิน"""
        # ✅ ใช้ production domain
        PRODUCTION_URL = 'https://npdhrms.com'
        
        for record in self:
            if record.rating_token:
                # ✅ ใช้ query parameter (?token=)
                record.rating_url = f"{PRODUCTION_URL}/rating/?token={record.rating_token}"
            else:
                record.rating_url = False
    
    # ========================================
    # JWT Token Functions
    # ========================================
    
    def _create_jwt_token(self, booking_id, customer_email=''):
        """สร้าง JWT Token"""
        issued_at = int(datetime.now().timestamp())
        exp = issued_at + self.TOKEN_EXPIRY
        
        payload = {
            'booking_id': booking_id,
            'customer_email': customer_email,
            'iat': issued_at,
            'exp': exp
        }
        
        # Header
        header = {'alg': 'HS256', 'typ': 'JWT'}
        header_b64 = base64.urlsafe_b64encode(json.dumps(header).encode()).decode().rstrip('=')
        payload_b64 = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip('=')
        
        # Signature
        message = f"{header_b64}.{payload_b64}"
        signature = hmac.new(
            self.JWT_SECRET.encode(),
            message.encode(),
            hashlib.sha256
        ).digest()
        signature_b64 = base64.urlsafe_b64encode(signature).decode().rstrip('=')
        
        jwt_token = f"{message}.{signature_b64}"
        _logger.info(f"✅ JWT Token created for booking_id={booking_id}")
        return jwt_token
    
    def _verify_jwt_token(self, token):
        """ตรวจสอบ JWT Token"""
        try:
            parts = token.split('.')
            if len(parts) != 3:
                _logger.warning(f"❌ Invalid token format")
                return None
            
            header_b64, payload_b64, signature_b64 = parts
            
            # Verify Signature
            message = f"{header_b64}.{payload_b64}"
            signature = hmac.new(
                self.JWT_SECRET.encode(),
                message.encode(),
                hashlib.sha256
            ).digest()
            signature_calc = base64.urlsafe_b64encode(signature).decode().rstrip('=')
            
            if not hmac.compare_digest(signature_b64, signature_calc):
                _logger.warning(f"❌ Token signature invalid")
                return None
            
            # Decode Payload
            payload_json = base64.urlsafe_b64decode(payload_b64 + '==')
            payload = json.loads(payload_json)
            
            # Check Expiration
            if payload['exp'] < int(datetime.now().timestamp()):
                _logger.warning(f"❌ Token expired")
                return None
            
            _logger.info(f"✅ JWT Token verified: booking_id={payload['booking_id']}")
            return payload
        except Exception as e:
            _logger.error(f"❌ Token verification error: {e}")
            return None
    
    # ========================================
    # API Methods (สำหรับ PHP API)
    # ========================================
    
    @api.model
    def get_rating_info(self, token):
        """ดึงข้อมูล Rating (รองรับ JWT + UUID Token)"""
        _logger.info(f"🔍 get_rating_info called with token={token[:50] if len(token) > 50 else token}")
        
        try:
            # ✅ ลองตรวจสอบ JWT Token ก่อน
            jwt_payload = self._verify_jwt_token(token)
            if jwt_payload:
                booking_id = jwt_payload.get('booking_id')
                rating = self.with_user(False).search([
                    ('booking_id', '=', booking_id),
                    ('state', '!=', 'expired')
                ], limit=1)
            else:
                # ✅ ถ้า JWT fail ให้ลองใช้ UUID token (เก่า)
                rating = self.with_user(False).search([
                    ('rating_token', '=', token),
                    ('state', '!=', 'expired')
                ], limit=1)
            
            if not rating:
                _logger.warning(f"⚠️ Rating not found for token={token[:50]}")
                return {'error': 'Invalid or expired rating link'}
            
            _logger.info(f"✅ Rating found: Booking={rating.booking_id.name}, State={rating.state}")
            
            # ✅ Format rating_date ให้อ่านได้ (Thai format + UTC+7)
            rating_date_str = ''
            if rating.rating_date:
                from datetime import datetime, timedelta, timezone
                
                dt = rating.rating_date
                
                # ✅ แปลง UTC เป็น UTC+7 (Thailand)
                if dt.tzinfo is None:
                    # ถ้าไม่มี timezone info ให้สมมติว่า UTC
                    dt_utc = dt.replace(tzinfo=timezone.utc)
                else:
                    dt_utc = dt
                
                # เปลี่ยนเป็น UTC+7
                thai_tz = timezone(timedelta(hours=7))
                dt_thai = dt_utc.astimezone(thai_tz)
                
                # แปลง Gregorian year เป็น Buddhist year (เพิ่ม 543)
                thai_year = dt_thai.year + 543
                
                # ชื่อเดือนไทย
                thai_months = {
                    1: 'มกราคม', 2: 'กุมภาพันธ์', 3: 'มีนาคม', 4: 'เมษายน',
                    5: 'พฤษภาคม', 6: 'มิถุนายน', 7: 'กรกฎาคม', 8: 'สิงหาคม',
                    9: 'กันยายน', 10: 'ตุลาคม', 11: 'พฤศจิกายน', 12: 'ธันวาคม'
                }
                
                month_name = thai_months.get(dt_thai.month, '')
                rating_date_str = f"{dt_thai.day:02d} {month_name} {thai_year} เวลา {dt_thai.hour:02d}:{dt_thai.minute:02d}:{dt_thai.second:02d}"
            
            return {
                'booking_id': rating.booking_id.id,
                'booking_name': rating.booking_id.name,
                'driver_name': rating.driver_name or 'N/A',
                'pickup_location': rating.pickup_location or 'N/A',
                'destination': rating.destination or 'N/A',
                'customer_name': rating.customer_name or 'N/A',
                'state': rating.state,
                'rating_id': rating.id,
                'rating_stars': rating.rating_stars or '0',
                'customer_comment': rating.customer_comment or '',
                'rating_date': rating_date_str,  # ✅ เพิ่มวันที่
            }
        except Exception as e:
            _logger.error(f"❌ Error in get_rating_info: {e}", exc_info=True)
            return {'error': str(e)}
    
    @api.model
    def submit_rating(self, token, rating_stars, customer_comment=''):
        """
        บันทึกการประเมินจากลูกค้า
        
        ✅ รองรับ:
        - submit_rating('token_xxx', 5, 'good comment')  ← positional args from PHP/RPC
        - submit_rating(token='xxx', rating_stars=5)     ← keyword args from Python
        """
        _logger.info(f"📝 submit_rating called: token={token[:20] if token else None}, rating_stars={rating_stars}")
        
        try:
            if not token:
                raise ValidationError(_('Missing token'))
            if rating_stars is None:
                raise ValidationError(_('Missing rating_stars'))
            
            # Convert to int if string
            try:
                rating_stars = int(rating_stars)
            except (ValueError, TypeError):
                raise ValidationError(_('Invalid rating_stars'))
            
            # ✅ ลองตรวจสอบ JWT Token ก่อน
            jwt_payload = self._verify_jwt_token(token)
            if jwt_payload:
                booking_id = jwt_payload.get('booking_id')
                rating = self.with_user(False).search([
                    ('booking_id', '=', booking_id),
                ], limit=1)
            else:
                # ✅ ถ้า JWT fail ให้ลองใช้ UUID token (เก่า)
                rating = self.with_user(False).search([
                    ('rating_token', '=', token),
                ], limit=1)
            
            if not rating:
                _logger.warning(f"⚠️ Rating submission failed: Invalid token")
                raise ValidationError(_('Invalid rating link'))
            
            if rating.state == 'expired':
                _logger.warning(f"⚠️ Rating submission failed: Link expired")
                raise ValidationError(_('This rating link has expired'))
            
            # ✅ Validate rating stars
            if rating_stars < 1 or rating_stars > 5:
                raise ValidationError(_('Invalid rating (1-5 only)'))
            
            # ✅ บันทึกการประเมิน
            rating.write({
                'rating_stars': str(rating_stars),
                'customer_comment': customer_comment or '',
                'rating_date': fields.Datetime.now(),
                'state': 'done',
            })
            
            _logger.info(f"✅ Rating submitted: Booking={rating.booking_id.name}, Stars={rating_stars}")
            
            return {
                'success': True,
                'message': 'ขอบคุณสำหรับการประเมิน',
                'booking_name': rating.booking_id.name,
                'driver_name': rating.driver_name or 'N/A',
            }
        except ValidationError:
            raise
        except Exception as e:
            _logger.error(f"❌ Error in submit_rating: {e}", exc_info=True)
            raise ValidationError(_(f'Error: {str(e)}'))
    
    # ========================================
    # Action Methods
    # ========================================
    
    def action_send_rating_link(self):
        """ส่ง Link ประเมินให้ลูกค้า"""
        self.ensure_one()
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Rating Link'),
                'message': _('Link: %s') % self.rating_url,
                'type': 'success',
                'sticky': False,
            }
        }
    
    def action_mark_expired(self):
        """ทำเครื่องหมายว่าหมดอายุ"""
        for record in self:
            if record.state == 'pending':
                record.state = 'expired'


class VehicleBooking(models.Model):
    _inherit = 'vehicle.booking'
    
    rating_ids = fields.One2many('delivery.rating', 'booking_id', string='การประเมิน')
    rating_count = fields.Integer('จำนวนการประเมิน', compute='_compute_rating_count')
    latest_rating = fields.Float('คะแนนล่าสุด', compute='_compute_latest_rating', store=True)
    
    @api.depends('rating_ids')
    def _compute_rating_count(self):
        for record in self:
            record.rating_count = len(record.rating_ids.filtered(lambda r: r.state == 'done'))
    
    @api.depends('rating_ids.rating_value', 'rating_ids.state')
    def _compute_latest_rating(self):
        for record in self:
            done_ratings = record.rating_ids.filtered(lambda r: r.state == 'done')
            if done_ratings:
                record.latest_rating = done_ratings[0].rating_value
            else:
                record.latest_rating = 0.0
    
    def action_create_rating_link(self):
        """สร้าง Rating Link - สร้าง record ให้อัตโนมัติ"""
        self.ensure_one()
        
        if self.state != 'done':
            raise ValidationError(_('สามารถสร้าง Rating Link ได้เฉพาะงานที่เสร็จสิ้นแล้ว'))
        
        # ✅ ตรวจสอบว่ามี rating อยู่แล้วหรือไม่
        existing_rating = self.env['delivery.rating'].search([
            ('booking_id', '=', self.id)
        ], limit=1)
        
        if existing_rating:
            # ✅ มี rating อยู่แล้ว - แสดง existing rating
            _logger.info(f"✅ Rating already exists for booking {self.name}")
            return {
                'name': _('📝 Link ประเมินความพึงพอใจ (มีอยู่แล้ว)'),
                'type': 'ir.actions.act_window',
                'res_model': 'delivery.rating',
                'res_id': existing_rating.id,
                'view_mode': 'form',
                'target': 'new',
            }
        else:
            # ✅ ไม่มี rating - สร้างใหม่
            new_rating = self.env['delivery.rating'].create({
                'booking_id': self.id,
            })
            
            _logger.info(f"✅ New rating created for booking {self.name}, token={new_rating.rating_token}")
            
            # ✅ แสดง success notification
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Link สร้างสำเร็จ'),
                    'message': _('Link ประเมินความพึงพอใจ:\n%s') % new_rating.rating_url,
                    'type': 'success',
                    'sticky': False,
                }
            }
    
    def action_view_ratings(self):
        """ดูประวัติการประเมินทั้งหมด"""
        self.ensure_one()
        return {
            'name': _('ประวัติการประเมิน'),
            'type': 'ir.actions.act_window',
            'res_model': 'delivery.rating',
            'view_mode': 'tree,form',
            'domain': [('booking_id', '=', self.id)],
            'context': {'default_booking_id': self.id},
        }
