from odoo import api, fields, models

class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'

    notes = fields.Html('Terms and Conditions', default=lambda self: self.env['ir.config_parameter'].sudo().get_param('job_card_management.purchase_default_terms', default=''))

    def button_confirm(self):
        res = super(PurchaseOrder, self).button_confirm()
        for order in self:
            try:
                # Use standard action to create the bill (leaves it in Draft)
                invoice_action = order.with_context(create_bill=True).action_create_invoice()
                if invoice_action and invoice_action.get('res_id'):
                    invoice = self.env['account.move'].browse(invoice_action['res_id'])
                    default_terms = self.env['ir.config_parameter'].sudo().get_param('job_card_management.purchase_default_terms', default='')
                    if default_terms:
                        invoice.narration = default_terms
            except Exception:
                pass
        return res
