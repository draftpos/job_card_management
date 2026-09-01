from odoo import models, fields

class ProcurementRejectWizard(models.TransientModel):
    _name = 'procurement.reject.wizard'
    _description = 'Procurement Reject Wizard'

    procurement_id = fields.Many2one('procurement', string='Requisition', required=True)
    reason = fields.Text(string='Rejection Reason', required=True)
    reject_type = fields.Selection([('requisition', 'Requisition'), ('po', 'Purchase Order')], required=True)

    def action_reject(self):
        for wiz in self:
            if wiz.reject_type == 'requisition':
                wiz.procurement_id.state = 'rejected'
                wiz.procurement_id.message_post(body=f"Requisition Rejected: {wiz.reason}")
            elif wiz.reject_type == 'po':
                wiz.procurement_id.state = 'po_rejected'
                wiz.procurement_id.message_post(body=f"Purchase Orders Rejected: {wiz.reason}")
                # Cancel linked draft POs
                pos = self.env['purchase.order'].search([
                    ('origin', '=', wiz.procurement_id.name), 
                    ('state', 'in', ['draft', 'sent', 'to approve'])
                ])
                for po in pos:
                    po.button_cancel()
