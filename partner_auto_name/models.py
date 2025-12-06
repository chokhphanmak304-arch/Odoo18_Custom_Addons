# -*- coding: utf-8 -*-

from odoo import models, api


class ResPartner(models.Model):
    _inherit = 'res.partner'

    @api.model_create_multi
    def create(self, vals_list):
        """Auto-generate name from firstname and lastname before create"""
        for vals in vals_list:
            # ถ้า name ไม่มีค่า ให้สร้างจาก firstname + lastname
            if not vals.get('name'):
                name_parts = []
                if vals.get('firstname'):
                    name_parts.append(vals['firstname'])
                if vals.get('lastname'):
                    name_parts.append(vals['lastname'])
                
                # ตั้งค่า name
                vals['name'] = ' '.join(name_parts) if name_parts else 'Partner'
        
        return super().create(vals_list)
