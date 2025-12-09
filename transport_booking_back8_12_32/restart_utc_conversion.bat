@echo off
echo ========================================
echo RESTART ODOO - UTC Timezone Fix
echo ========================================
echo.
echo Fix: Convert Thailand time to UTC before saving
echo Example: 2025-11-21 22:07:33 (TH) - 7 hours = 2025-11-21 15:07:33 (UTC)
echo Odoo will then display: 2025-11-21 22:07:33 (in Thailand timezone)
echo.
echo ========================================
cd /d "C:\Program Files\Odoo 18.0.20251009"
echo.
echo Stopping Odoo service...
net stop "Odoo 18.0-20251009"
timeout /t 3

echo.
echo Starting Odoo service...
net start "Odoo 18.0-20251009"

echo.
echo ========================================
echo Odoo restarted successfully!
echo ========================================
echo.
echo Now test completing another delivery.
echo Check that planned_end_date_t is displayed correctly!
echo.
pause
