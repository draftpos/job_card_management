from odoo import models, fields, api, _
from odoo.exceptions import UserError

class PrintInvoiceWizard(models.TransientModel):
    _name = 'print.invoice.wizard'
    _description = 'Print Invoice Wizard'

    job_card_id = fields.Many2one('job.card', string='Job Card', required=True)
    has_insurance = fields.Boolean(string='Has Insurance Invoice')
    print_selection = fields.Selection([
        ('customer', 'Customer Invoice'),
        ('insurance', 'Insurance Invoice'),
        ('both', 'Both')
    ], string='Print Selection', default='customer', required=True)

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        active_id = self.env.context.get('active_id')
        if active_id and self.env.context.get('active_model') == 'job.card':
            job_card = self.env['job.card'].browse(active_id)
            res['job_card_id'] = job_card.id
            if job_card.insurance_invoice_id:
                res['has_insurance'] = True
                res['print_selection'] = 'both'
            else:
                res['has_insurance'] = False
                res['print_selection'] = 'customer'
        return res

    def action_print(self):
        self.ensure_one()
        invoice_ids = []
        
        if self.print_selection in ['customer', 'both'] and self.job_card_id.customer_invoice_id:
            invoice_ids.append(self.job_card_id.customer_invoice_id.id)
            
        if self.print_selection in ['insurance', 'both'] and self.job_card_id.insurance_invoice_id:
            invoice_ids.append(self.job_card_id.insurance_invoice_id.id)
            
        if not invoice_ids:
            raise UserError(_('No invoices found to print based on your selection.'))
            
        return self.env.ref('job_card_management.action_report_custom_invoice').report_action(invoice_ids)
