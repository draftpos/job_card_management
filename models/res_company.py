# -*- coding: utf-8 -*-
from odoo import models, fields


class ResCompany(models.Model):
    _inherit = 'res.company'

    hao_bank_currency_id = fields.Many2one('res.currency', string="Bank Currency")


class HaoBankDetail(models.Model):
    _inherit = 'hao.bank.detail'

    currency_id = fields.Many2one('res.currency', string="Currency")
    parent_id = fields.Many2one('res.company', string="Parent Company", related='company_id.parent_id', store=False)
