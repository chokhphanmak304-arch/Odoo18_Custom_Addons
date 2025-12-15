-- =====================================================
-- SQL Script: อัพเดท has_app_delivery และ delivery_source
-- สำหรับข้อมูลเก่าที่มีอยู่แล้ว
-- =====================================================

-- 1. เพิ่ม column ถ้ายังไม่มี (Odoo จะสร้างให้อัตโนมัติเมื่อ update module)
-- ALTER TABLE vehicle_booking ADD COLUMN IF NOT EXISTS has_app_delivery BOOLEAN DEFAULT FALSE;
-- ALTER TABLE vehicle_booking ADD COLUMN IF NOT EXISTS delivery_source VARCHAR;

-- 2. อัพเดท bookings ที่มีประวัติจาก App
UPDATE vehicle_booking vb
SET 
    has_app_delivery = TRUE,
    delivery_source = 'app'
WHERE EXISTS (
    SELECT 1 FROM delivery_history dh 
    WHERE dh.booking_id = vb.id 
    AND dh.source = 'app'
);

-- 3. อัพเดท bookings ที่มีประวัติจาก Odoo เท่านั้น (ไม่มีจาก App)
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

-- 4. ตรวจสอบผลลัพธ์
SELECT 
    delivery_source,
    has_app_delivery,
    COUNT(*) as total
FROM vehicle_booking
WHERE delivery_source IS NOT NULL
GROUP BY delivery_source, has_app_delivery;

-- 5. ดูรายละเอียด bookings ที่มีประวัติจาก App
SELECT 
    vb.id,
    vb.name as booking_name,
    vb.has_app_delivery,
    vb.delivery_source,
    dh.source as history_source,
    dh.completion_date
FROM vehicle_booking vb
JOIN delivery_history dh ON dh.booking_id = vb.id
WHERE dh.source = 'app'
ORDER BY dh.completion_date DESC
LIMIT 20;
