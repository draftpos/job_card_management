# -*- coding: utf-8 -*-
from odoo import models, fields, api


def _format_uppercase(name_val):
    if isinstance(name_val, str):
        return name_val.upper()
    elif isinstance(name_val, dict):
        return {k: (v.upper() if isinstance(v, str) else v) for k, v in name_val.items()}
    return name_val


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    @api.model
    def _is_auto_uppercase_product_name_enabled(self):
        param = self.env['ir.config_parameter'].sudo().get_param(
            'job_card_management.auto_uppercase_product_name', False
        )
        return bool(param and str(param).strip().lower() in ('1', 'true', 'yes', 't'))

    @api.onchange('name')
    def _onchange_name_uppercase(self):
        if self.name and self._is_auto_uppercase_product_name_enabled() and isinstance(self.name, str):
            self.name = self.name.upper()

    @api.model_create_multi
    def create(self, vals_list):
        if self._is_auto_uppercase_product_name_enabled():
            for vals in vals_list:
                if 'name' in vals and vals['name']:
                    vals['name'] = _format_uppercase(vals['name'])
        return super().create(vals_list)

    def write(self, vals):
        if 'name' in vals and vals['name'] and self._is_auto_uppercase_product_name_enabled():
            vals['name'] = _format_uppercase(vals['name'])
        return super().write(vals)


class ProductProduct(models.Model):
    _inherit = 'product.product'

    @api.onchange('name')
    def _onchange_name_uppercase(self):
        if self.name and self.env['product.template']._is_auto_uppercase_product_name_enabled() and isinstance(self.name, str):
            self.name = self.name.upper()

    @api.model_create_multi
    def create(self, vals_list):
        if self.env['product.template']._is_auto_uppercase_product_name_enabled():
            for vals in vals_list:
                if 'name' in vals and vals['name']:
                    vals['name'] = _format_uppercase(vals['name'])
        return super().create(vals_list)

    def write(self, vals):
        if 'name' in vals and vals['name'] and self.env['product.template']._is_auto_uppercase_product_name_enabled():
            vals['name'] = _format_uppercase(vals['name'])
        return super().write(vals)
