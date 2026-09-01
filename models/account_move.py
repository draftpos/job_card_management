from odoo import models, fields, api

class AccountMove(models.Model):
    _inherit = 'account.move'
    _order = 'id desc'

    is_insurance_invoice = fields.Boolean(string='Is Insurance Invoice', default=False)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('move_type') == 'in_invoice' and not vals.get('narration'):
                vals['narration'] = self.env['ir.config_parameter'].sudo().get_param('job_card_management.purchase_default_terms', default='')
        return super().create(vals_list)
