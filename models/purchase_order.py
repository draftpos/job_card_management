from odoo import api, fields, models, _
from odoo.exceptions import UserError

class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'
    _order = 'id desc'

    notes = fields.Html('Terms and Conditions', default=lambda self: self.env['ir.config_parameter'].sudo().get_param('job_card_management.purchase_default_terms', default=''))
    
    closing_reason = fields.Text(string="Closing Reason", copy=False)
    is_amended = fields.Boolean(string="Is Amended", copy=False, default=False)

    def button_approve(self):
        # Restrict approval to authorized users
        if not self.env.user.has_group('job_card_management.group_can_approve_purchase_order'):
            raise UserError(_("You do not have the required permissions to approve Purchase Orders."))
        return super(PurchaseOrder, self).button_approve()

    def button_confirm(self):
        res = super(PurchaseOrder, self).button_confirm()
        return res

    def action_manual_close(self):
        """Action to trigger the manual close wizard"""
        self.ensure_one()
        return {
            'name': _('Close Purchase Order'),
            'type': 'ir.actions.act_window',
            'res_model': 'purchase.order.close.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_purchase_order_id': self.id}
        }
        
    def action_amend_supplier(self):
        """Action to trigger the amend supplier wizard"""
        self.ensure_one()
        return {
            'name': _('Amend Supplier'),
            'type': 'ir.actions.act_window',
            'res_model': 'purchase.order.amend.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_purchase_order_id': self.id, 'default_old_partner_id': self.partner_id.id}
        }

class PurchaseOrderLine(models.Model):
    _inherit = 'purchase.order.line'

    def write(self, vals):
        # Check for price hikes on approved POs
        if 'price_unit' in vals:
            for line in self:
                if line.order_id.state in ['purchase', 'done'] and vals['price_unit'] > line.price_unit:
                    # Reset PO to 'to approve'
                    line.order_id.write({'state': 'to approve'})
                    line.order_id.message_post(
                        body=_("PO reset to 'To Approve' because the price of %s was increased from %s to %s.", line.product_id.display_name, line.price_unit, vals['price_unit']),
                        subtype_xmlid='mail.mt_note'
                    )
        return super(PurchaseOrderLine, self).write(vals)
