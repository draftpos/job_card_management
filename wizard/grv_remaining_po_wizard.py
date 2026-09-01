from odoo import api, fields, models, _
from odoo.exceptions import UserError

class GRVRemainingPOWizard(models.TransientModel):
    _name = 'grv.remaining.po.wizard'
    _description = 'Source Remaining Items from New Supplier'

    picking_id = fields.Many2one('stock.picking', string='GRV', required=True)
    purchase_id = fields.Many2one('purchase.order', string='Original PO', required=True)
    
    line_ids = fields.One2many('grv.remaining.po.wizard.line', 'wizard_id', string='Items to Source')

    @api.model
    def default_get(self, fields_list):
        res = super(GRVRemainingPOWizard, self).default_get(fields_list)
        purchase_id_val = self.env.context.get('default_purchase_id') or res.get('purchase_id')
        if purchase_id_val:
            purchase_id = self.env['purchase.order'].browse(purchase_id_val)
            lines = []
            for line in purchase_id.order_line:
                remaining = line.product_qty - line.qty_received
                if remaining > 0:
                    lines.append((0, 0, {
                        'purchase_line_id': line.id,
                        'product_id': line.product_id.id,
                        'remaining_qty': remaining,
                        'new_qty': remaining,
                        'new_supplier_id': purchase_id.partner_id.id,
                        'unit_price': line.price_unit,
                    }))
            if lines:
                res['line_ids'] = lines
        return res

    def action_confirm(self):
        self.ensure_one()
        # Group by supplier
        suppliers = {}
        for line in self.line_ids:
            if not line.new_supplier_id:
                raise UserError(_("Please select a new supplier for all lines."))
            if line.new_qty <= 0:
                continue
            if line.new_qty > line.remaining_qty:
                raise UserError(_("You cannot source more than the remaining quantity."))
                
            supplier = line.new_supplier_id
            if supplier not in suppliers:
                suppliers[supplier] = []
            suppliers[supplier].append(line)
            
        if not suppliers:
            raise UserError(_("No items selected to source."))

        # Create new POs
        new_pos = self.env['purchase.order']
        for supplier, lines in suppliers.items():
            po_vals = {
                'partner_id': supplier.id,
                'origin': self.purchase_id.origin, # Keep original job card / procurement reference
                'order_line': [],
            }
            for line in lines:
                po_vals['order_line'].append((0, 0, {
                    'product_id': line.product_id.id,
                    'product_qty': line.new_qty,
                    'price_unit': line.unit_price,
                    'name': line.product_id.name,
                }))
            
            new_po = self.env['purchase.order'].create(po_vals)
            new_po.button_confirm() # This generates the new GRV
            new_pos |= new_po
            
            # Cancel the remaining backorders on the original PO?
            # Actually, standard Odoo backorder wizard handles it.
            # But we should explicitly cancel the original PO's remaining lines or just leave them open?
            # To cancel the remaining lines on original PO:
            for line in lines:
                if line.purchase_line_id:
                    orig_line = line.purchase_line_id
                    orig_line.product_qty = orig_line.qty_received
                else:
                    # Fallback in case of missing purchase_line_id (legacy data)
                    orig_lines = self.purchase_id.order_line.filtered(lambda l: l.product_id == line.product_id)
                    for orig_line in orig_lines:
                        orig_line.product_qty = orig_line.qty_received

        new_pickings = new_pos.mapped('picking_ids')
        if len(new_pickings) == 1:
            return {
                'name': _('New GRV'),
                'type': 'ir.actions.act_window',
                'res_model': 'stock.picking',
                'view_mode': 'form',
                'res_id': new_pickings.id,
            }
        return {
            'name': _('New GRVs'),
            'type': 'ir.actions.act_window',
            'res_model': 'stock.picking',
            'view_mode': 'list,form',
            'domain': [('id', 'in', new_pickings.ids)],
        }


class GRVRemainingPOWizardLine(models.TransientModel):
    _name = 'grv.remaining.po.wizard.line'
    _description = 'Source Remaining Items Line'

    wizard_id = fields.Many2one('grv.remaining.po.wizard')
    purchase_line_id = fields.Many2one('purchase.order.line', string='Original Line')
    product_id = fields.Many2one('product.product', string='Product', readonly=True)
    remaining_qty = fields.Float(string='Remaining Qty', readonly=True)
    new_qty = fields.Float(string='Qty to Source')
    new_supplier_id = fields.Many2one('res.partner', string='New Supplier', required=True, domain="[('supplier_rank', '>=', 1)]")
    unit_price = fields.Float(string='Unit Price')
