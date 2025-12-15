# -*- coding: utf-8 -*-
"""
Migration: เพิ่ม has_app_delivery, delivery_source fields
Version: 18.0.2.6.0
"""
import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    """Post-migration: คำนวณ has_app_delivery สำหรับ records ที่มีอยู่แล้ว"""
    if not version:
        return

    _logger.info("🔄 [Migration 18.0.2.6.0] Starting post-migration...")

    # อัพเดท has_app_delivery และ delivery_source สำหรับ bookings ที่มีประวัติจาก app
    cr.execute("""
        UPDATE vehicle_booking vb
        SET 
            has_app_delivery = TRUE,
            delivery_source = 'app'
        WHERE EXISTS (
            SELECT 1 FROM delivery_history dh 
            WHERE dh.booking_id = vb.id 
            AND dh.source = 'app'
        );
    """)
    app_count = cr.rowcount
    _logger.info(f"✅ Updated {app_count} bookings with app delivery history")

    # อัพเดท delivery_source = 'odoo' สำหรับ bookings ที่มีประวัติจาก odoo เท่านั้น
    cr.execute("""
        UPDATE vehicle_booking vb
        SET 
            has_app_delivery = FALSE,
            delivery_source = 'odoo'
        WHERE NOT EXISTS (
            SELECT 1 FROM delivery_history dh 
            WHERE dh.booking_id = vb.id 
            AND dh.source = 'app'
        )
        AND EXISTS (
            SELECT 1 FROM delivery_history dh 
            WHERE dh.booking_id = vb.id 
            AND dh.source = 'odoo'
        );
    """)
    odoo_count = cr.rowcount
    _logger.info(f"✅ Updated {odoo_count} bookings with odoo-only delivery history")

    _logger.info("✅ [Migration 18.0.2.6.0] Completed successfully!")
