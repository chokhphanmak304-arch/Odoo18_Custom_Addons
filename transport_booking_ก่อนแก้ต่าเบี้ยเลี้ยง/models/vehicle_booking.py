# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
import logging
import requests
import json

_logger = logging.getLogger(__name__)


class VehicleBooking(models.Model):
    _name = 'vehicle.booking'
    _description = 'Vehicle Booking / จองคิวรถขนส่ง'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'booking_date desc'

    # ข้อมูลพื้นฐาน
    name = fields.Char('เลขที่จอง', copy=False, readonly=True,
                       default='New', tracking=True)
    booking_date = fields.Datetime('วันที่จอง', default=fields.Datetime.now,
                                   required=True, tracking=True)

    # เชื่อมโยงกับคำสั่งขนส่ง
    # transport_order_id = fields.Many2one('transport.order',
    #                                      string='คำสั่งขนส่ง',
    #                                      required=True,
    #                                      tracking=True,
    #                                      domain=[('state', '=', 'sale')])

    transport_order_id = fields.Many2one(
        'transport.order',
        string='คำสั่งขนส่ง',
        required=True,
        tracking=True
        # ❌ ลบ domain ออกไป - ใช้ method แทน
    )

    # ข้อมูลลูกค้า
    partner_id = fields.Many2one('res.partner',
                                 string='ลูกค้า',
                                 related='transport_order_id.partner_id',
                                 store=True,
                                 readonly=True)
    delivery_employee_name = fields.Char('พนักงานส่งของ',
                                         related='transport_order_id.delivery_employee_name',
                                         store=True,
                                         readonly=True)

    branch_id = fields.Many2one('res.branch', string='สาขา', related='transport_order_id.branch_id', tracking=True,
                                readonly=True)
    travel_expenses = fields.Float('ค่าเที่ยว', digits=(10, 2), tracking=True, store=True, copy=False, related='transport_order_id.trip_allowance', readonly=True)
    daily_allowance = fields.Float('ค่าเบี้ยเลี้ยง', digits=(10, 2), tracking=True, store=True, copy=False,
                                   related='transport_order_id.daily_allowance', readonly=True)

    # ฟิลด์ที่ดึงจาก Transport Order (readonly - ล๊อกไม่ให้แก้)
    pickup_location = fields.Text('สถานที่รับสินค้า', readonly=True, store=True, copy=False)
    destination = fields.Text('ปลายทาง', readonly=True, store=True, copy=False)
    distance_km = fields.Float('ระยะทาง (กม.)', digits=(10, 3), readonly=True, store=True, copy=False)
    shipping_cost = fields.Float('ค่าขนส่ง', digits=(10, 2), readonly=True, required=True, tracking=True, store=True,
                                 copy=False)
    total_weight_order = fields.Float('น้ำหนักรวม (กก.)', digits=(10, 2), readonly=True, store=True, copy=False,
                                      help='น้ำหนักรวมจากรายการสินค้าใน Transport Order')

    # GPS Coordinates สำหรับแผนที่นำทาง
    pickup_latitude = fields.Float('Pickup Latitude', digits=(10, 7), store=True, copy=False)
    pickup_longitude = fields.Float('Pickup Longitude', digits=(10, 7), store=True, copy=False)
    destination_latitude = fields.Float('Destination Latitude', digits=(10, 7), store=True, copy=False)
    destination_longitude = fields.Float('Destination Longitude', digits=(10, 7), store=True, copy=False)

    # ข้อมูลจาก Transport Order (readonly)
    currency_id = fields.Many2one('res.currency',
                                  string='สกุลเงิน',
                                  default=lambda self: self.env.company.currency_id,
                                  readonly=True)

    vehicle_type_name = fields.Char('ประเภทรถ',
                                    related='transport_order_id.vehicle_type_name',
                                    store=True,
                                    readonly=True)

    delivery_type = fields.Selection(
        string='ประเภทการจัดส่ง',
        selection=[
            ('customer', 'จัดส่งไปยังลูกค้า'),
            ('branch', 'จัดส่งมายังสาขา'),
        ],
        default='customer',
        related='transport_order_id.delivery_type',
        required=True,
        tracking=True, readonly=True
    )

    license_plate_name = fields.Char('ทะเบียนรถ (จาก Order)',
                                     related='transport_order_id.license_plate_name',
                                     store=True,
                                     readonly=True)

    # เชื่อมโยงกับระบบติดตามรถ GPS
    gps_vehicle_id = fields.Many2one('gps.vehicle.tracking',
                                     string='🛰️ ติดตามรถ GPS',
                                     compute='_compute_gps_vehicle',
                                     store=True,
                                     readonly=True,
                                     help='เชื่อมโยงกับระบบติดตามรถ GPS โดยอัตโนมัติจากทะเบียนรถ')
    gps_tracking_available = fields.Boolean('มีข้อมูล GPS',
                                            compute='_compute_gps_vehicle',
                                            store=True)
    gps_vehicle_speed = fields.Float('ความเร็วปัจจุบัน (กม./ชม.)',
                                     related='gps_vehicle_id.speed',
                                     readonly=True)
    gps_vehicle_status = fields.Char('สถานะรถ GPS',
                                     related='gps_vehicle_id.status_text',
                                     readonly=True)
    gps_last_update = fields.Datetime('GPS อัปเดตล่าสุด',
                                      related='gps_vehicle_id.utc_timestamp',
                                      readonly=True)

    # จัดสรรรถและคนขับ
    vehicle_id = fields.Many2one('fleet.vehicle',
                                 string='🚚 รถที่จัดส่ง',
                                 tracking=True,
                                 domain=[('vehicle_check_status', '=', 'available')])
    driver_id = fields.Many2one('vehicle.driver',
                                string='👤 คนขับ',
                                tracking=True)

    # ✅ ชื่อคนขับ (Computed Field)
    driver_name = fields.Char(
        string='ชื่อคนขับ',
        compute='_compute_driver_name',
        store=False
    )

    # Google Maps - Interactive Widget
    map_route = fields.Char('แผนที่เส้นทาง', compute='_compute_map_route',
                            inverse='_inverse_map_route', store=False)

    # ฟิลด์สำหรับเก็บข้อมูลเส้นทาง
    distance = fields.Char('ระยะทาง', readonly=True, store=True, copy=False)
    estimated_time = fields.Char('เวลาโดยประมาณ', readonly=True, store=True, copy=False)
    waypoints_json = fields.Text('Waypoints JSON', store=True, copy=False,
                                 help='เก็บจุดกึ่งกลางที่ผู้ใช้ลากเส้นทาง')

    # ฟิลด์ trigger สำหรับบังคับให้แผนที่อัพเดท (เปลี่ยนเป็น field ธรรมดา)
    map_trigger = fields.Char('Map Trigger', default='', store=True)
    route_version = fields.Integer('Route Version', default=0, store=True)

    # สถานะ
    state = fields.Selection([
        ('draft', '📝 ร่าง'),
        ('confirmed', '✅ ยืนยันการจอง'),
        ('in_progress', '🚚 กำลังขนส่ง'),
        ('done', '✔️ เสร็จสิ้น'),
        ('cancelled', '❌ ยกเลิก'),
    ], string='สถานะ', default='draft', required=True, tracking=True)

    # เพิ่มเติม
    planned_start_date = fields.Datetime('วันเวลาที่วางแปนออกเดินทาง')
    planned_end_date = fields.Datetime('วันเวลาที่วางแผนถึงปลายทาง')

    planned_start_date_t = fields.Datetime('วันเวลาออกเดินทางจริง', readonly=True, tracking=True)
    planned_end_date_t = fields.Datetime('วันเวลาที่ส่งจริง', readonly=True, tracking=True)

    note = fields.Html('หมายเหตุ')

    # ติดตามการขนส่ง
    tracking_status = fields.Selection([
        ('pending', 'รอออกเดินทาง'),
        ('picked_up', 'รับสินค้าแล้ว'),
        ('in_transit', 'อยู่ระหว่างขนส่ง'),
        ('near_destination', 'ใกล้ถึงปลายทาง'),
        ('delivered', 'ส่งถึงแล้ว'),
    ], string='สถานะการติดตาม', default='pending', tracking=True)

    actual_pickup_time = fields.Datetime('เวลารับสินค้าจริง', tracking=True)
    actual_delivery_time = fields.Datetime('เวลาส่งถึงจริง', tracking=True)
    current_location = fields.Char('ตำแหน่งปัจจุบัน')
    tracking_notes = fields.Text('บันทึกการติดตาม')
    pickup_photo = fields.Binary('รูปถ่ายสินค้าก่อนขนส่ง', attachment=True)
    delivery_photo = fields.Binary('รูปถ่ายหลักฐานการส่ง', attachment=True)
    receiver_name = fields.Char('ชื่อผู้รับ')
    receiver_signature = fields.Binary('ลายเซ็นผู้รับ', attachment=True)

    # 🎨 ข้อมูลลายน้ำจากแอป
    delivery_timestamp = fields.Datetime('เวลาส่งของ (GPS)', help='เวลาที่ถ่ายรูปหลักฐาน')
    delivery_latitude = fields.Float('ละติจูด GPS ส่งของ', digits=(10, 7), help='พิกัด GPS เมื่อส่งของ')
    delivery_longitude = fields.Float('ลองจิจูด GPS ส่งของ', digits=(10, 7), help='พิกัด GPS เมื่อส่งของ')

    # GPS Tracking
    current_latitude = fields.Float('Latitude ปัจจุบัน', digits=(10, 7))
    current_longitude = fields.Float('Longitude ปัจจุบัน', digits=(10, 7))
    gps_last_update = fields.Datetime('อัพเดท GPS ล่าสุด')
    tracking_history_ids = fields.One2many('vehicle.tracking.history', 'booking_id', string='ประวัติการติดตาม')

    # 📍 ความสัมพันธ์กับ vehicle.tracking
    tracking_ids = fields.One2many('vehicle.tracking', 'booking_id', string='จุดติดตาม GPS')

    # สำหรับ Smart Button
    tracking_count = fields.Integer('จำนวน Tracking', compute='_compute_tracking_count')

    # สำหรับแสดงแผนที่ tracking
    tracking_map_html = fields.Html('Tracking Map', compute='_compute_tracking_map_html', sanitize=False)

    expense_ids = fields.One2many('vehicle.booking.expense', 'booking_id', string='ค่าใช้จ่ายเพิ่มเติม')
    total_expense = fields.Float('รวมค่าใช้จ่ายเพิ่มเติม', compute='_compute_total_expense', store=True, digits=(12, 2))

    @api.onchange('transport_order_id')
    def _onchange_update_transport_order_domain(self):
        """ปรับ domain ของ transport_order_id ตามสาขาของผู้ใช้"""
        # Method นี้จะถูกเรียกเมื่อมีการเลือก transport_order_id
        pass  # Logic ของ domain จะถูกจัดการใน XML view หรือ JavaScript

    # ❌ วิธีที่ดีกว่า: ใช้ ir.rule สำหรับ record-level access control

    @api.model
    def _search(self, domain, offset=0, limit=None, order=None):
        """Override search เพื่อกรองตาม branch ของ user"""
        user = self.env.user

        _logger.debug(
            f"🔍 VehicleBooking._search | User: {user.name} | "
            f"Branch: {user.branch_id.name if user.branch_id else 'None'} | "
            f"show_all: {user.show_all_transport_booking_branches}"
        )

        # ✅ ถ้า user ไม่เลือก "แสดงทุกสาขา" AND มี branch กำหนด → กรองเฉพาะ branch นั้น
        if not user.show_all_transport_booking_branches and user.branch_id:
            branch_domain = [('branch_id', '=', user.branch_id.id)]
            domain = (domain or []) + branch_domain
            _logger.info(f"✅ Filtering by branch: {user.branch_id.name}")
        else:
            _logger.info(
                f"🌍 Showing all branches - "
                f"show_all_transport_booking_branches={user.show_all_transport_booking_branches}, "
                f"has_branch={bool(user.branch_id)}"
            )

        return super()._search(domain, offset=offset, limit=limit, order=order)

    @api.depends('expense_ids.amount')
    def _compute_total_expense(self):
        for rec in self:
            rec.total_expense = sum(rec.expense_ids.mapped('amount'))

    def _compute_tracking_count(self):
        """คำนวณจำนวน tracking records"""
        for record in self:
            if record._origin.id:
                record.tracking_count = self.env['vehicle.tracking'].search_count([
                    ('booking_id', '=', record._origin.id)
                ])
            else:
                record.tracking_count = 0

    def _compute_tracking_map_html(self):
        """สร้าง HTML สำหรับแสดงแผนที่ tracking"""
        for record in self:
            if record._origin.id:
                iframe_url = f"/tracking/map/{record._origin.id}"
                record.tracking_map_html = f'''
                    <div style="width: 100%; height: 500px; border: 1px solid #ddd; border-radius: 8px; overflow: hidden;">
                        <iframe src="{iframe_url}" 
                                style="width: 100%; height: 100%; border: none;" 
                                title="Real-time Tracking Map">
                        </iframe>
                    </div>
                '''
            else:
                record.tracking_map_html = '''
                    <div style="text-align: center; padding: 50px; color: #999;">
                        <p>บันทึกข้อมูลก่อนเพื่อดูแผนที่ติดตาม</p>
                    </div>
                '''

    @api.depends('driver_id')
    def _compute_driver_name(self):
        """✅ คำนวณชื่อคนขับจาก driver_id"""
        for record in self:
            if record.driver_id:
                record.driver_name = record.driver_id.name or f"ID: {record.driver_id.id}"
            else:
                record.driver_name = None

    @api.depends('license_plate_name')
    def _compute_gps_vehicle(self):
        """ค้นหารถจากระบบติดตาม GPS โดยใช้ทะเบียนรถ"""
        for record in self:
            record.gps_vehicle_id = False
            record.gps_tracking_available = False

            if record.license_plate_name:
                # ค้นหารถใน GPS tracking จากทะเบียน
                gps_vehicle = self.env['gps.vehicle.tracking'].search([
                    ('lpn', '=', record.license_plate_name)
                ], limit=1)

                if gps_vehicle:
                    record.gps_vehicle_id = gps_vehicle.id
                    record.gps_tracking_available = True
                    _logger.info(f"✅ พบรถ GPS: {record.license_plate_name} -> {gps_vehicle.device_name}")
                # ถ้าไม่เจอก็ไม่ต้องแสดง warning (ปกติ)

    def _geocode_address(self, address):
        """แปลง address เป็น latitude, longitude ด้วย Google Maps Geocoding API"""
        if not address or not address.strip():
            return None, None

        try:
            # ดึง API key
            api_key = self.env['ir.config_parameter'].sudo().get_param('google_maps_api_key')
            if not api_key:
                _logger.warning("⚠️ Google Maps API key not configured")
                return None, None

            # เรียก Google Maps Geocoding API
            url = "https://maps.googleapis.com/maps/api/geocode/json"
            params = {
                'address': address,
                'key': api_key,
                'language': 'th',  # ภาษาไทย
                'region': 'th'  # ประเทศไทย
            }

            _logger.info(f"🌍 Geocoding address: {address}")
            response = requests.get(url, params=params, timeout=10)

            if response.status_code == 200:
                data = response.json()
                if data.get('status') == 'OK' and data.get('results'):
                    location = data['results'][0]['geometry']['location']
                    lat = location.get('lat')
                    lng = location.get('lng')
                    _logger.info(f"✅ Geocoded: {address} → ({lat}, {lng})")
                    return lat, lng
                else:
                    _logger.warning(f"⚠️ Geocoding failed: {data.get('status')}")
            else:
                _logger.error(f"❌ Geocoding API error: {response.status_code}")

        except Exception as e:
            _logger.error(f"❌ Geocoding error: {str(e)}")

        return None, None

    @api.depends('pickup_location', 'destination')
    def _compute_map_route(self):
        """Dummy compute เพื่อให้ field พร้อมใช้กับ widget"""
        for record in self:
            record.map_route = 'ready'

    def _inverse_map_route(self):
        """Inverse method สำหรับ map_route - ไม่ต้องทำอะไร"""
        pass

    @api.model_create_multi
    def create(self, vals_list):
        """สร้างเอกสารใหม่ - ยังไม่กำหนดเลขรัน (รอยืนยันการจอง)"""
        for vals in vals_list:
            # ไม่สร้างเลขรันตอน create - ให้เป็น 'New' ก่อน
            if not vals.get('name') or vals.get('name') == 'New':
                vals['name'] = 'New'

            # 🌍 Auto-geocode addresses เมื่อสร้างใหม่
            if vals.get('pickup_location') and not vals.get('pickup_latitude'):
                pickup_lat, pickup_lng = self._geocode_address(vals['pickup_location'])
                if pickup_lat and pickup_lng:
                    vals['pickup_latitude'] = pickup_lat
                    vals['pickup_longitude'] = pickup_lng
                    _logger.info(
                        f"✅ [CREATE] Geocoded pickup: {vals['pickup_location']} → ({pickup_lat}, {pickup_lng})")

            if vals.get('destination') and not vals.get('destination_latitude'):
                dest_lat, dest_lng = self._geocode_address(vals['destination'])
                if dest_lat and dest_lng:
                    vals['destination_latitude'] = dest_lat
                    vals['destination_longitude'] = dest_lng
                    _logger.info(f"✅ [CREATE] Geocoded destination: {vals['destination']} → ({dest_lat}, {dest_lng})")

        return super().create(vals_list)

    def write(self, vals):
        """อัพเดทเอกสาร - auto-geocode ถ้ามีการเปลี่ยนแปลง address"""
        # 🌍 Auto-geocode ถ้ามี address ใหม่
        if vals.get('pickup_location'):
            # Force geocode ถ้า:
            # 1. ไม่มี pickup_latitude/longitude ใน vals (ยังไม่เคยมี)
            # 2. หรือถูกส่งมาเป็น False (force reset)
            # 3. หรือถูกส่งมาเป็น 0.0 (invalid coordinate)
            should_geocode_pickup = (
                    'pickup_latitude' not in vals or
                    vals.get('pickup_latitude') is False or
                    vals.get('pickup_latitude') == 0.0 or
                    'pickup_longitude' not in vals or
                    vals.get('pickup_longitude') is False or
                    vals.get('pickup_longitude') == 0.0
            )

            if should_geocode_pickup:
                pickup_lat, pickup_lng = self._geocode_address(vals['pickup_location'])
                if pickup_lat and pickup_lng:
                    vals['pickup_latitude'] = pickup_lat
                    vals['pickup_longitude'] = pickup_lng
                    _logger.info(f"✅ [WRITE] Geocoded pickup: {vals['pickup_location']} → ({pickup_lat}, {pickup_lng})")

        if vals.get('destination'):
            # Force geocode ถ้า:
            # 1. ไม่มี destination_latitude/longitude ใน vals (ยังไม่เคยมี)
            # 2. หรือถูกส่งมาเป็น False (force reset)
            # 3. หรือถูกส่งมาเป็น 0.0 (invalid coordinate)
            should_geocode_dest = (
                    'destination_latitude' not in vals or
                    vals.get('destination_latitude') is False or
                    vals.get('destination_latitude') == 0.0 or
                    'destination_longitude' not in vals or
                    vals.get('destination_longitude') is False or
                    vals.get('destination_longitude') == 0.0
            )

            if should_geocode_dest:
                dest_lat, dest_lng = self._geocode_address(vals['destination'])
                if dest_lat and dest_lng:
                    vals['destination_latitude'] = dest_lat
                    vals['destination_longitude'] = dest_lng
                    _logger.info(f"✅ [WRITE] Geocoded destination: {vals['destination']} → ({dest_lat}, {dest_lng})")

        return super().write(vals)

    @api.onchange('transport_order_id')
    def _onchange_transport_order(self):
        """ดึงข้อมูลจาก Transport Order"""
        if self.transport_order_id:
            _logger.info("=" * 50)
            _logger.info("🔄 Transport Order Changed: %s", self.transport_order_id.name)
            _logger.info("📍 Pickup Location: %s", self.transport_order_id.pickup_location)
            _logger.info("📍 Destination: %s", self.transport_order_id.destination)
            _logger.info("📏 Distance: %s km", self.transport_order_id.distance_km)

            self.pickup_location = self.transport_order_id.pickup_location
            self.destination = self.transport_order_id.destination
            self.distance_km = self.transport_order_id.distance_km
            self.total_weight_order = self.transport_order_id.total_weight_order

            _logger.info("⚖️ Total Weight: %s kg", self.transport_order_id.total_weight_order)

            # 🌍 Geocode addresses เป็น coordinates อัตโนมัติ
            if self.pickup_location:
                pickup_lat, pickup_lng = self._geocode_address(self.pickup_location)
                if pickup_lat and pickup_lng:
                    self.pickup_latitude = pickup_lat
                    self.pickup_longitude = pickup_lng
                    _logger.info(f"📍 Pickup coordinates: ({pickup_lat}, {pickup_lng})")

            if self.destination:
                dest_lat, dest_lng = self._geocode_address(self.destination)
                if dest_lat and dest_lng:
                    self.destination_latitude = dest_lat
                    self.destination_longitude = dest_lng
                    _logger.info(f"📍 Destination coordinates: ({dest_lat}, {dest_lng})")

            # ✅ เคลียร์ waypoints เมื่อเปลี่ยน Transport Order ใหม่
            self.waypoints_json = False
            _logger.info("🧹 Cleared waypoints for new Transport Order")

            # ✅ เช็ค shipping_cost_m ก่อน ถ้ามีค่าให้ใช้ ถ้าไม่มีให้ใช้ shipping_cost
            # if self.transport_order_id.shipping_cost_m:
            #     self.shipping_cost = self.transport_order_id.shipping_cost_m
            #
            #     _logger.info("💰 Using shipping_cost_m: %s", self.transport_order_id.shipping_cost_m)
            # else:
            #     self.shipping_cost = self.transport_order_id.shipping_cost
            #     _logger.info("💰 Using shipping_cost: %s", self.transport_order_id.shipping_cost)

            if self.transport_order_id.use_special_delivery_zero and self.transport_order_id.shipping_cost_m == 0:
                # 🔹 กรณีส่งฟรีพิเศษ และ shipping_cost_m = 0
                self.shipping_cost = self.transport_order_id.shipping_cost_m
                _logger.info("💰 Using shipping_cost_m (special delivery zero case): %.2f",
                             self.transport_order_id.shipping_cost_m)

            elif not self.transport_order_id.use_special_delivery_zero and self.transport_order_id.shipping_cost_m > 0:
                # 🔹 กรณีไม่ใช้ส่งฟรี และมีค่าขนส่งพิเศษ > 0
                self.shipping_cost = self.transport_order_id.shipping_cost_m
                _logger.info("💰 Using shipping_cost_m (>0 w/o special): %.2f", self.transport_order_id.shipping_cost_m)

            elif not self.transport_order_id.use_special_delivery_zero and self.transport_order_id.shipping_cost_m == 0:
                # 🔹 กรณีไม่ใช้ส่งฟรี และไม่มีค่าขนส่งพิเศษ → ใช้ค่าปกติ
                self.shipping_cost = self.transport_order_id.shipping_cost
                _logger.info("💰 Using shipping_cost (m==0 w/o special): %.2f", self.transport_order_id.shipping_cost)

            else:
                # 🔹 fallback เผื่อข้อมูลไม่ครบ
                self.shipping_cost = self.transport_order_id.shipping_cost
                _logger.info("💰 Fallback using shipping_cost: %.2f", self.transport_order_id.shipping_cost)

            # 🆕 ดึงค่าเที่ยวและสร้างรายการค่าใช้จ่ายเริ่มต้น
            # travel_expenses เป็น related field จะอัพเดทอัตโนมัติ
            _logger.info("🚗 Travel Expenses from order (trip_allowance): %.2f", self.travel_expenses or 0.0)
            
            # ✅ เคลียร์ค่าใช้จ่ายเก่าก่อน
            self.expense_ids = [(5, 0, 0)]
            
            # ✅ สร้างรายการค่าเที่ยวเริ่มต้น (ถ้ามีค่า > 0)
            if self.travel_expenses > 0:
                expense_vals = {
                    'expense_type': 'travel',
                    'description': f'ค่าเที่ยวจาก {self.transport_order_id.name}',
                    'expense_date': fields.Date.context_today(self),
                    'amount': self.travel_expenses,
                }
                self.expense_ids = [(0, 0, expense_vals)]
                _logger.info("✅ Created initial travel expense: %.2f", self.travel_expenses)

            _logger.info("=" * 50)

            # เพิ่ม route_version เพื่อ trigger map widget
            self.route_version = (self.route_version or 0) + 1

            # อัพเดท map_trigger โดยตรงเพื่อ force widget re-render
            self.map_trigger = f"{self.pickup_location or ''}|{self.destination or ''}|{self.route_version}"

            _logger.info("🔄 Route version updated to: %s", self.route_version)
            _logger.info("🗺️ Map trigger updated to: %s", self.map_trigger)

            if self.transport_order_id.license_plate_name:
                vehicle = self.env['fleet.vehicle'].search([
                    ('license_plate', '=', self.transport_order_id.license_plate_name),
                    ('vehicle_check_status', '=', 'available')
                ], limit=1)
                if vehicle:
                    self.vehicle_id = vehicle.id
                    _logger.info("🚚 Vehicle found: %s", vehicle.license_plate)

            # 👤 ค้นหาคนขับอัตโนมัติจาก delivery_employee_name
            if self.transport_order_id.delivery_employee_name:
                driver = self.env['vehicle.driver'].search([
                    ('name', '=', self.transport_order_id.delivery_employee_name)
                ], limit=1)
                if driver:
                    self.driver_id = driver.id
                    _logger.info("👤 Driver found: %s (ID: %s)", driver.name, driver.id)
                else:
                    self.driver_id = False
                    _logger.info("⚠️ Driver not found for name: %s", self.transport_order_id.delivery_employee_name)
            else:
                self.driver_id = False
        else:
            _logger.info("⚠️ No transport order selected")

    def action_confirm(self):
        """ยืนยันการจอง - สร้างเลขรันเอกสารและเปลี่ยนสถานะรถเป็น 'ติดจอง' (reserved)"""
        for record in self:
            if not record.vehicle_id:
                raise ValidationError('กรุณาเลือกรถก่อนยืนยันการจอง')
            if not record.driver_id:
                raise ValidationError('กรุณาเลือกคนขับก่อนยืนยันการจอง')

            # สร้างเลขรันเอกสาร (ถ้ายังเป็น 'New')
            if record.name == 'New':
                new_name = self.env['ir.sequence'].next_by_code('vehicle.booking')
                if not new_name:
                    raise ValidationError('ไม่สามารถสร้างเลขที่จองได้ กรุณาติดต่อผู้ดูแลระบบ')
                record.name = new_name
                _logger.info("📝 Created booking number: %s", new_name)

            # อัพเดทสถานะรถเป็น 'ติดจอง'
            record.vehicle_id.write({'vehicle_check_status': 'reserved'})
            record.write({'state': 'confirmed'})

    def action_reset_to_draft(self):
        """รีเซ็ตเป็นร่าง - เปลี่ยนสถานะรถเป็น 'พร้อมใช้' (available) และเปลี่ยนสถานะเอกสารเป็น draft"""
        for record in self:
            if record.state == 'confirmed':
                if record.vehicle_id:
                    # คืนสถานะรถเป็น 'พร้อมใช้'
                    record.vehicle_id.write({'vehicle_check_status': 'available'})
                    _logger.info("🔄 Vehicle %s status reset to available", record.vehicle_id.license_plate)

                # เปลี่ยนสถานะเป็นร่าง
                record.write({'state': 'draft'})
                _logger.info("🔄 Booking %s reset to draft", record.name)

    def action_start(self):
        """เริ่มขนส่ง - เปลี่ยนสถานะรถเป็น 'กำลังจัดส่ง' (in_delivery)"""
        for record in self:
            if record.vehicle_id:
                # อัพเดทสถานะรถเป็น 'กำลังจัดส่ง'
                record.vehicle_id.write({'vehicle_check_status': 'in_delivery'})
        self.write({
            'state': 'in_progress',
            'tracking_status': 'in_transit'  # อัพเดทสถานะติดตาม
        })

    def start_job_with_photo(self, photo_base64):
        """เริ่มงานพร้อมอัพโหลดรูปถ่ายสินค้า (สำหรับ Mobile App)"""
        self.ensure_one()

        try:
            _logger.info("📸 [start_job_with_photo] Starting job %s with photo", self.name)

            # บันทึกรูปถ่าย + เวลาออกเดินทางจริง
            self.write({
                'pickup_photo': photo_base64,
                'actual_pickup_time': fields.Datetime.now(),
                'planned_start_date_t': fields.Datetime.now(),  # ✅ เพิ่มบรรทึกเวลาออกเดินทางจริง
            })
            _logger.info("✅ [start_job_with_photo] Photo saved successfully")
            _logger.info("✅ [start_job_with_photo] planned_start_date_t recorded: %s", fields.Datetime.now())

            # เริ่มงาน
            self.action_start()
            _logger.info("✅ [start_job_with_photo] Job started successfully")

            # 📍 สร้าง tracking record เริ่มต้น (ณ จุดรับสินค้า)
            try:
                if self.pickup_latitude and self.pickup_longitude:
                    # ✅ ใช้ driver_id จากตัว booking แทน current_user
                    if not self.driver_id:
                        _logger.warning("⚠️ [start_job_with_photo] No driver assigned to booking %s, skipping tracking",
                                        self.name)
                    else:
                        tracking_vals = {
                            'booking_id': self.id,
                            'driver_id': self.driver_id.id,  # ✅ ใช้ vehicle.driver.id
                            'latitude': self.pickup_latitude,
                            'longitude': self.pickup_longitude,
                            'timestamp': fields.Datetime.now(),
                            'address': self.pickup_location or '',
                            'notes': 'เริ่มงาน - รับสินค้าที่ต้นทาง',
                            'speed': 0.0,
                        }
                        tracking = self.env['vehicle.tracking'].create(tracking_vals)
                        _logger.info("✅ [start_job_with_photo] Initial tracking created: %s at (%s, %s)",
                                     tracking.id, self.pickup_latitude, self.pickup_longitude)
                else:
                    _logger.warning("⚠️ [start_job_with_photo] Missing pickup coordinates, skipping tracking")
            except Exception as e:
                _logger.error("❌ [start_job_with_photo] Error creating tracking: %s", str(e))
                # ไม่ throw error - ให้งานดำเนินต่อแม้ tracking จะไม่สำเร็จ

            return True

        except Exception as e:
            _logger.error("❌ [start_job_with_photo] Error: %s", str(e))
            raise ValidationError(f"ไม่สามารถเริ่มงานได้: {str(e)}")

    def action_done(self):
        """เสร็จสิ้น - เปลี่ยนสถานะรถเป็น 'พร้อมใช้' (available) และสร้างประวัติการจัดส่ง"""
        for record in self:
            # if record.vehicle_id:
            #     # อัพเดทสถานะรถเป็น 'พร้อมใช้'
            #     record.vehicle_id.write({'vehicle_check_status': 'available'})

            if record.vehicle_id:
                # อัพเดทสถานะรถเป็น 'พร้อมใช้'
                update_vals = {'vehicle_check_status': 'available'}
                
                # ✅ อัปเดต next_assignation_date ด้วย planned_end_date_t (วันเวลาที่ส่งจริง)
                if record.planned_end_date_t:
                    update_vals['next_assignation_date'] = record.planned_end_date_t
                    _logger.info(f"✅ Updated next_assignation_date to {record.planned_end_date_t} for vehicle {record.vehicle_id.license_plate}")
                
                record.vehicle_id.write(update_vals)

            record.write({
                'state': 'done',
                'tracking_status': 'delivered',  # อัพเดทสถานะติดตาม
                'actual_delivery_time': fields.Datetime.now(),  # บันทึกเวลาส่งถึงจริง
                'planned_end_date_t': fields.Datetime.now()
            })

            # 📜 สร้างประวัติการจัดส่ง
            try:
                _logger.info(f"📜 Creating delivery history for booking: {record.name}")
                history = self.env['delivery.history'].create_from_booking(record)
                if history:
                    _logger.info(f"✅ Delivery history created: {history.id}")
                else:
                    _logger.warning(f"⚠️ Failed to create delivery history for {record.name}")
            except Exception as e:
                _logger.error(f"❌ Error creating delivery history: {str(e)}")

    def action_cancel(self):
        """ยกเลิก - เปลี่ยนสถานะรถเป็น 'พร้อมใช้' (available) และสร้างประวัติ (ถ้ามีการเริ่มงาน)"""
        for record in self:
            if record.vehicle_id and record.state in ['confirmed', 'in_progress']:
                # อัพเดทสถานะรถเป็น 'พร้อมใช้'
                record.vehicle_id.write({'vehicle_check_status': 'available'})
            record.write({'state': 'cancelled'})

            # 📜 สร้างประวัติถ้ามีการเริ่มงานแล้ว (มีรูปถ่าย หรือ actual_pickup_time)
            if record.actual_pickup_time or record.pickup_photo:
                try:
                    _logger.info(f"📜 Creating cancelled delivery history for booking: {record.name}")
                    history = self.env['delivery.history'].create_from_booking(record)
                    if history:
                        _logger.info(f"✅ Cancelled delivery history created: {history.id}")
                except Exception as e:
                    _logger.error(f"❌ Error creating cancelled delivery history: {str(e)}")

    def unlink(self):
        """ลบได้เฉพาะสถานะ 'ร่าง' เท่านั้น"""
        for record in self:
            if record.state != 'draft':
                raise ValidationError(
                    _('ไม่สามารถลบการจองได้!\n'
                      'สามารถลบได้เฉพาะสถานะ "ร่าง" เท่านั้น\n'
                      'การจองนี้อยู่ในสถานะ: %s') % dict(record._fields['state'].selection).get(record.state)
                )
        return super(VehicleBooking, self).unlink()

    # ฟังก์ชันสำหรับอัพเดทสถานะติดตาม
    def action_mark_picked_up(self):
        """บันทึกว่ารับสินค้าแล้ว"""
        self.write({
            'tracking_status': 'picked_up',
            'actual_pickup_time': fields.Datetime.now(),
            'planned_start_date_t': fields.Datetime.now()
        })

    def action_mark_near_destination(self):
        """บันทึกว่าใกล้ถึงปลายทาง"""
        self.write({'tracking_status': 'near_destination'})

    def action_mark_delivered(self):
        """บันทึกว่าส่งถึงแล้ว"""
        self.write({
            'tracking_status': 'delivered',
            'actual_delivery_time': fields.Datetime.now(),
            'planned_end_date_t': fields.Datetime.now()
        })

    def action_view_tracking(self):
        """เปิดดู tracking records ของ booking นี้พร้อมแสดง countdown timer จากค่า tracking_interval"""
        self.ensure_one()

        # ✅ ดึงค่า tracking_interval จากตาราง tracking.settings
        settings = self.env['tracking.settings'].search([
            ('user_id', '=', self.env.user.id)
        ], limit=1)

        # ถ้าไม่มี settings ให้สร้างใหม่ด้วยค่าเริ่มต้น 5 นาที
        if not settings:
            settings = self.env['tracking.settings'].create({
                'user_id': self.env.user.id,
                'tracking_interval': 5  # ✅ ค่าเริ่มต้น 5 นาที (ตรงกับ default ใน tracking.settings model)
            })

        # เตรียมข้อมูล countdown timer
        tracking_interval_seconds = (settings.tracking_interval or 1) * 60  # แปลงนาทีเป็นวินาที

        _logger.info(f"📍 [Action] Opening tracking view for {self.name}")
        _logger.info(
            f"⏱️  [Action] tracking_interval from DB: {settings.tracking_interval} minutes ({tracking_interval_seconds} seconds)")

        return {
            'name': f'📍 ติดตามตำแหน่ง - {self.name}',
            'type': 'ir.actions.act_window',
            'res_model': 'vehicle.tracking',
            'view_mode': 'list,form,graph',
            'domain': [('booking_id', '=', self.id)],
            'context': {
                'default_booking_id': self.id,
                'default_driver_id': self.driver_id.id if self.driver_id else False,
                'tracking_interval': settings.tracking_interval,  # ✅ ส่งค่า tracking_interval ไปใน context
                'tracking_interval_seconds': tracking_interval_seconds,  # ✅ ส่งค่าแปลงเป็นวินาทีด้วย
            },
        }

    def action_open_tracking_map(self):
        """เปิดแผนที่ติดตามแบบ Food Delivery Style"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_url',
            'url': f'/tracking/map/{self.id}',
            'target': 'new',
        }

    def action_view_gps_tracking(self):
        """เปิดหน้าติดตามรถ GPS Real-time"""
        self.ensure_one()

        if not self.gps_vehicle_id:
            # แสดง notification ถ้าไม่พบรถ GPS
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'ไม่พบข้อมูล GPS',
                    'message': f'ไม่พบรถทะเบียน "{self.license_plate_name}" ในระบบติดตาม GPS',
                    'type': 'warning',
                    'sticky': False,
                }
            }

        # เปิดหน้าแผนที่ GPS แบบ Real-time
        return {
            'type': 'ir.actions.act_url',
            'url': f'/vehicle_tracking/map/{self.gps_vehicle_id.id}',
            'target': 'new',
        }

    def action_open_gps_vehicle_form(self):
        """เปิดฟอร์มข้อมูลรถ GPS"""
        self.ensure_one()

        if not self.gps_vehicle_id:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'ไม่พบข้อมูล GPS',
                    'message': f'ไม่พบรถทะเบียน "{self.license_plate_name}" ในระบบติดตาม GPS',
                    'type': 'warning',
                }
            }

        return {
            'name': 'ข้อมูลรถ GPS',
            'type': 'ir.actions.act_window',
            'res_model': 'gps.vehicle.tracking',
            'res_id': self.gps_vehicle_id.id,
            'view_mode': 'form',
            'target': 'current',
        }


# ==================== ประวัติการติดตาม GPS ====================
class VehicleTrackingHistory(models.Model):
    _name = 'vehicle.tracking.history'
    _description = 'Vehicle Tracking History'
    _order = 'timestamp desc'

    booking_id = fields.Many2one('vehicle.booking', string='Booking', required=True, ondelete='cascade')
    timestamp = fields.Datetime('เวลา', default=fields.Datetime.now, required=True)
    latitude = fields.Float('Latitude', digits=(10, 7), required=True)
    longitude = fields.Float('Longitude', digits=(10, 7), required=True)
    speed = fields.Float('ความเร็ว (km/h)')
    heading = fields.Float('ทิศทาง (องศา)')
    address = fields.Char('ที่อยู่')


# ==================== การตั้งค่าการติดตาม ====================
class TrackingConfig(models.Model):
    _name = 'tracking.config'
    _description = 'Tracking Configuration'

    name = fields.Char('ชื่อการตั้งค่า', required=True, default='Default')
    refresh_interval = fields.Integer('เวลา Refresh (วินาที)', default=10, required=True,
                                      help='ความถี่ในการอัพเดทตำแหน่งบนแผนที่')
    show_route_history = fields.Boolean('แสดงเส้นทางที่ผ่านมา', default=True)
    auto_center_map = fields.Boolean('ปรับแผนที่ตามรถอัตโนมัติ', default=True)
    show_speed = fields.Boolean('แสดงความเร็ว', default=True)
    active = fields.Boolean('Active', default=True)

    _sql_constraints = [
        ('name_unique', 'UNIQUE(name)', 'ชื่อการตั้งค่าต้องไม่ซ้ำกัน'),
    ]

    @api.constrains('refresh_interval')
    def _check_refresh_interval(self):
        for record in self:
            if record.refresh_interval < 5:
                raise ValidationError('เวลา Refresh ต้องไม่น้อยกว่า 5 วินาที')
            if record.refresh_interval > 300:
                raise ValidationError('เวลา Refresh ต้องไม่เกิน 300 วินาที (5 นาที)')


class VehicleBookingExpense(models.Model):
    _name = 'vehicle.booking.expense'
    _description = 'รายการค่าใช้จ่ายเพิ่มเติมต่อเที่ยว'
    _order = 'expense_date desc, id desc'

    booking_id = fields.Many2one('vehicle.booking', string='เอกสารจองรถ', required=True, ondelete='cascade', index=True)

    # ✅ เปลี่ยนเป็น select (Selection)
    expense_type = fields.Selection([
        ('fuel', 'ค่าน้ำมันเชื้อเพลิง'),
        ('travel', 'ค่าเที่ยว'),
        ('toll', 'ค่าทางด่วน'),
        ('parking', 'ค่าจอดรถ'),
        ('food', 'ค่าอาหาร'),
        ('misc', 'ค่าใช้จ่ายอื่นๆ'),
    ], string='ชื่อค่าใช้จ่าย', required=True, default='fuel')

    description = fields.Char('รายละเอียดเพิ่มเติม')
    expense_date = fields.Date('วันที่', default=fields.Date.context_today, required=True)
    amount = fields.Float('จำนวนเงิน', digits=(10, 2), required=True)

    # ฟิลด์เฉพาะค่าน้ำมัน (แสดงเมื่อเลือก fuel)
    is_fuel = fields.Boolean('เป็นค่าน้ำมัน?', compute='_compute_is_fuel', store=False)
    fuel_liters = fields.Float('ปริมาณน้ำมัน (ลิตร)')
    fuel_price_per_liter = fields.Float('ราคา/ลิตร')

    @api.depends('expense_type')
    def _compute_is_fuel(self):
        for rec in self:
            rec.is_fuel = (rec.expense_type == 'fuel')

    @api.onchange('expense_type', 'fuel_liters', 'fuel_price_per_liter')
    def _onchange_fuel_compute_amount(self):
        for rec in self:
            if rec.expense_type == 'fuel' and rec.fuel_liters and rec.fuel_price_per_liter:
                rec.amount = round(rec.fuel_liters * rec.fuel_price_per_liter, 2)