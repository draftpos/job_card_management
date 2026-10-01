from odoo import api, fields, models, _
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)

class StockPicking(models.Model):
    _inherit = 'stock.picking'
    _order = 'id desc'

    has_remaining_po_qty = fields.Boolean(
        string='Has Remaining PO Qty', 
        compute='_compute_has_remaining_po_qty'
    )

    @api.depends('purchase_id.order_line.qty_received', 'purchase_id.order_line.product_qty')
    def _compute_has_remaining_po_qty(self):
        for picking in self:
            if picking.purchase_id:
                picking.has_remaining_po_qty = any(
                    line.product_qty > line.qty_received 
                    for line in picking.purchase_id.order_line
                )
            else:
                picking.has_remaining_po_qty = False

    def button_validate(self):
        res = super(StockPicking, self).button_validate()
        for picking in self:
            if picking.state == 'done' and picking.picking_type_code == 'incoming' and picking.purchase_id:
                picking._auto_create_vendor_bill()
        return res
    
    def _action_done(self):
        res = super(StockPicking, self)._action_done()
        for picking in self:
            if picking.picking_type_code == 'incoming' and picking.purchase_id:
                picking._auto_create_vendor_bill()
        return res

    def _auto_create_vendor_bill(self):
        self.ensure_one()
        order = self.purchase_id
        if not order:
            return

        try:
            invoice_action = order.with_context(create_bill=True).action_create_invoice()
            if invoice_action and invoice_action.get('res_id'):
                invoice = self.env['account.move'].browse(invoice_action['res_id'])
                
                default_terms = self.env['ir.config_parameter'].sudo().get_param('job_card_management.purchase_default_terms', default='')
                if default_terms:
                    invoice.narration = default_terms
                    
                if not invoice.invoice_date:
                    invoice.invoice_date = fields.Date.context_today(order)
                invoice.action_post()
        except Exception as e:
            _logger.error("Error auto-invoicing GRV %s for PO %s: %s", self.name, order.name, e)

    def action_source_remaining_supplier(self):
        self.ensure_one()
        if self.state != 'done':
            raise UserError(_("You can only source remaining items after validating the current receipt."))
        
        remaining_lines = self.purchase_id.order_line.filtered(lambda l: l.product_qty > l.qty_received)
        if not remaining_lines:
            raise UserError(_("There are no remaining items to source."))

        return {
            'name': _('Source Remaining from New Supplier'),
            'type': 'ir.actions.act_window',
            'res_model': 'grv.remaining.po.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_picking_id': self.id,
                'default_purchase_id': self.purchase_id.id,
            }
        }


class StockMove(models.Model):
    _inherit = 'stock.move'

    po_ordered_qty = fields.Float(
        string='PO Ordered Qty', 
        related='purchase_line_id.product_qty', 
        readonly=True
    )
    po_remaining_qty = fields.Float(
        string='PO Remaining Qty', 
        compute='_compute_po_remaining_qty'
    )

    @api.depends('purchase_line_id.product_qty', 'purchase_line_id.qty_received')
    def _compute_po_remaining_qty(self):
        for move in self:
            if move.purchase_line_id:
                move.po_remaining_qty = max(0.0, move.purchase_line_id.product_qty - move.purchase_line_id.qty_received)
            else:
                move.po_remaining_qty = 0.0
