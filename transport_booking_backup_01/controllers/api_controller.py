# -*- coding: utf-8 -*-
import json
import logging
from odoo import http
from odoo.http import request

_logger = logging.getLogger(__name__)


class VehicleBookingAPIController(http.Controller):
    """API Controller สำหรับแอปมือถือดึงข้อมูล Vehicle Booking"""

    @http.route('/api/v1/vehicle_booking/get_bookings', 
                type='json', 
                auth='public', 
                methods=['POST'], 
                csrf=False)
    def get_bookings(self, **kwargs):
        """ดึงข้อมูล Vehicle Booking พร้อมฟิวด์ที่แอปต้องการ
        
        Request Body:
        {
            "fields": ["name", "state", "planned_start_date_t", "travel_expenses", ...],
            "domain": [["state", "=", "confirmed"]],
            "limit": 50
        }
        """
        try:
            # ดึงข้อมูลจาก request body
            request_data = request.get_json_data() or {}
            fields = request_data.get('fields', [])
            domain = request_data.get('domain', [])
            limit = request_data.get('limit', 50)

            _logger.info(f"📥 [API] Fetching bookings with fields: {fields}")
            _logger.info(f"📥 [API] Domain: {domain}")

            # ค้นหา bookings
            bookings = request.env['vehicle.booking'].search(
                domain,
                limit=limit,
                order='planned_start_date asc'
            )

            # สร้าง response
            result = []
            for booking in bookings:
                booking_data = {
                    'id': booking.id,
                    'name': booking.name,
                }
                
                # เพิ่มฟิวด์ที่ขอ
                for field in fields:
                    try:
                        value = getattr(booking, field, None)
                        
                        # จัดการ many2one fields (แปลงเป็น [id, name])
                        if hasattr(booking._fields[field], 'relation'):
                            if value:
                                booking_data[field] = [value.id, value.name or '']
                            else:
                                booking_data[field] = False
                        # จัดการ datetime fields
                        elif field in ['planned_start_date_t', 'actual_pickup_time', 
                                      'actual_delivery_time', 'planned_end_date_t']:
                            if value:
                                booking_data[field] = value.isoformat()
                            else:
                                booking_data[field] = None
                        # จัดการ fields อื่นๆ
                        else:
                            booking_data[field] = value
                            
                    except Exception as e:
                        _logger.warning(f"⚠️ Error getting field {field}: {str(e)}")
                        booking_data[field] = None
                
                result.append(booking_data)

            _logger.info(f"✅ [API] Returned {len(result)} bookings")
            
            return {
                'success': True,
                'data': result,
                'count': len(result),
            }

        except Exception as e:
            _logger.error(f"❌ [API] Error fetching bookings: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'message': 'ไม่สามารถดึงข้อมูลการจองได้'
            }

    @http.route('/api/v1/vehicle_booking/get/<int:booking_id>', 
                type='json', 
                auth='public', 
                methods=['GET'], 
                csrf=False)
    def get_booking_detail(self, booking_id, **kwargs):
        """ดึงข้อมูล Vehicle Booking รายการเดียว
        
        Response:
        {
            "id": 1,
            "name": "BK-001",
            "state": "confirmed",
            "planned_start_date_t": "2025-11-17T10:00:00",
            "travel_expenses": 500.00,
            ...
        }
        """
        try:
            booking = request.env['vehicle.booking'].browse(booking_id)
            
            if not booking.exists():
                return {
                    'success': False,
                    'error': 'ไม่พบการจองนี้',
                    'booking_id': booking_id
                }

            _logger.info(f"📥 [API] Fetching booking detail: {booking.name}")

            # สร้าง response ที่มีฟิวด์ที่แอปต้องการ
            booking_data = {
                'id': booking.id,
                'name': booking.name,
                'state': booking.state,
                'booking_date': booking.booking_date.isoformat() if booking.booking_date else None,
                'transport_order_id': [booking.transport_order_id.id, booking.transport_order_id.name] if booking.transport_order_id else False,
                'partner_name': booking.partner_id.name if booking.partner_id else None,
                'delivery_employee_name': booking.delivery_employee_name,
                'pickup_location': booking.pickup_location,
                'destination': booking.destination,
                'distance_km': booking.distance_km,
                'shipping_cost': booking.shipping_cost,
                'total_weight_order': booking.total_weight_order,
                'vehicle_id': [booking.vehicle_id.id, booking.vehicle_id.name] if booking.vehicle_id else False,
                'driver_id': [booking.driver_id.id, booking.driver_id.name] if booking.driver_id else False,
                'license_plate_name': booking.license_plate_name,
                'planned_start_date': booking.planned_start_date.isoformat() if booking.planned_start_date else None,
                'planned_end_date': booking.planned_end_date.isoformat() if booking.planned_end_date else None,
                # ✅ ฟิวด์ที่แอปต้องการใช้
                'planned_start_date_t': booking.planned_start_date_t.isoformat() if booking.planned_start_date_t else None,
                'planned_end_date_t': booking.planned_end_date_t.isoformat() if booking.planned_end_date_t else None,
                'actual_pickup_time': booking.actual_pickup_time.isoformat() if booking.actual_pickup_time else None,
                'actual_delivery_time': booking.actual_delivery_time.isoformat() if booking.actual_delivery_time else None,
                'travel_expenses': booking.travel_expenses,
                # GPS Coordinates
                'pickup_latitude': booking.pickup_latitude,
                'pickup_longitude': booking.pickup_longitude,
                'destination_latitude': booking.destination_latitude,
                'destination_longitude': booking.destination_longitude,
                # Tracking info
                'tracking_status': booking.tracking_status,
                'current_location': booking.current_location,
                'current_latitude': booking.current_latitude,
                'current_longitude': booking.current_longitude,
            }

            _logger.info(f"✅ [API] Booking detail retrieved: {booking.name}")
            
            return {
                'success': True,
                'data': booking_data,
            }

        except Exception as e:
            _logger.error(f"❌ [API] Error fetching booking detail: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'message': 'ไม่สามารถดึงข้อมูลการจองได้'
            }

    @http.route('/api/v1/vehicle_booking/update_expenses', 
                type='json', 
                auth='public', 
                methods=['POST'], 
                csrf=False)
    def update_travel_expenses(self, **kwargs):
        """อัพเดท travel_expenses สำหรับการจองโดยแอปมือถือ
        
        Request Body:
        {
            "booking_id": 1,
            "travel_expenses": 500.00,
            "remark": "เชื้อเพลิง"
        }
        """
        try:
            request_data = request.get_json_data() or {}
            booking_id = request_data.get('booking_id')
            travel_expenses = request_data.get('travel_expenses', 0)
            remark = request_data.get('remark', '')

            if not booking_id:
                return {
                    'success': False,
                    'error': 'ต้องระบุ booking_id',
                }

            booking = request.env['vehicle.booking'].browse(booking_id)
            
            if not booking.exists():
                return {
                    'success': False,
                    'error': 'ไม่พบการจองนี้',
                    'booking_id': booking_id
                }

            _logger.info(f"📝 [API] Updating travel_expenses for {booking.name}: {travel_expenses}")

            # อัพเดท travel_expenses
            booking.write({
                'travel_expenses': travel_expenses,
            })

            # บันทึกลงใน tracking_notes ถ้ามี remark
            if remark:
                current_notes = booking.tracking_notes or ''
                updated_notes = f"{current_notes}\n💰 ค่าเที่ยวอัพเดท: {travel_expenses} - {remark}" if current_notes else f"💰 ค่าเที่ยวอัพเดท: {travel_expenses} - {remark}"
                booking.write({'tracking_notes': updated_notes})

            _logger.info(f"✅ [API] travel_expenses updated successfully")

            return {
                'success': True,
                'message': 'อัพเดทค่าเที่ยวสำเร็จ',
                'booking_id': booking_id,
                'travel_expenses': travel_expenses,
            }

        except Exception as e:
            _logger.error(f"❌ [API] Error updating travel_expenses: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'message': 'ไม่สามารถอัพเดทค่าเที่ยวได้'
            }
