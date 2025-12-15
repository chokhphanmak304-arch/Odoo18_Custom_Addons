# -*- coding: utf-8 -*-
"""
Script: อัพเดท has_app_delivery และ delivery_source สำหรับข้อมูลเก่า
วิธีใช้: รันใน Odoo Shell หรือ Scheduled Action
"""
import logging

_logger = logging.getLogger(__name__)


def update_existing_bookings(env):
    """อัพเดท has_app_delivery สำหรับ bookings ที่มีอยู่แล้ว"""
    
    _logger.info("🔄 Starting update has_app_delivery for existing bookings...")
    
    # ดึง bookings ทั้งหมดที่มี delivery_history
    bookings = env['vehicle.booking'].search([])
    
    updated_count = 0
    app_count = 0
    odoo_count = 0
    
    for booking in bookings:
        # ค้นหา delivery history ของ booking นี้
        histories = env['delivery.history'].search([
            ('booking_id', '=', booking.id)
        ])
        
        if histories:
            # เช็คว่ามี source = 'app' หรือไม่
            app_histories = histories.filtered(lambda h: h.source == 'app')
            
            if app_histories:
                booking.write({
                    'has_app_delivery': True,
                    'delivery_source': 'app'
                })
                app_count += 1
            else:
                booking.write({
                    'has_app_delivery': False,
                    'delivery_source': 'odoo'
                })
                odoo_count += 1
            
            updated_count += 1
    
    _logger.info(f"✅ Updated {updated_count} bookings")
    _logger.info(f"   📱 App: {app_count}")
    _logger.info(f"   🖥️ Odoo: {odoo_count}")
    
    return {
        'total': updated_count,
        'app': app_count,
        'odoo': odoo_count
    }


# สำหรับรันใน Odoo Shell:
# from odoo.addons.transport_booking.update_has_app_delivery import update_existing_bookings
# update_existing_bookings(env)
