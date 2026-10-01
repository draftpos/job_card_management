from odoo import api, fields, models

class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    job_card_default_terms = fields.Html(
        string='Default Terms and Conditions',
        help="Default terms and conditions added to new quotations."
    )
    
    purchase_default_terms = fields.Html(
        string='Purchase Terms',
        help='Default terms and conditions for purchase orders.'
    )
    customer_invoice_default_terms = fields.Html(
        string='Customer Invoice Terms',
        help='Default terms and conditions for customer invoices.'
    )
    insurance_invoice_default_terms = fields.Html(
        string='Insurance Invoice Terms',
        help='Default terms and conditions for insurance invoices.'
    )
    
    allow_service_requisition = fields.Boolean(
        string="Allow Consumables/Sundries in Requisitions",
        config_parameter='job_card_management.allow_service_requisition',
        default=False
    )
    
    # Quotation Print Settings
    print_customer_full_details = fields.Boolean(
        string='Print Full Customer Details on Quotations',
        config_parameter='job_card_management.print_customer_full_details',
        default=False
    )
    print_customer_tin = fields.Boolean(
        string='Show TIN Number',
        config_parameter='job_card_management.print_customer_tin',
        default=True
    )
    print_customer_phone = fields.Boolean(
        string='Show Phone',
        config_parameter='job_card_management.print_customer_phone',
        default=True
    )
    print_customer_email = fields.Boolean(
        string='Show Email',
        config_parameter='job_card_management.print_customer_email',
        default=True
    )
    print_customer_address = fields.Boolean(
        string='Show Address',
        config_parameter='job_card_management.print_customer_address',
        default=True
    )

    # Pick Slip Print Settings
    hide_company_details_pick_slip = fields.Boolean(
        string='Hide Company Details on Pick Slip',
        config_parameter='job_card_management.hide_company_details_pick_slip',
        default=False,
        help='If enabled, company address/phone/email will NOT be printed on the Pick Slip.'
    )

    # Vehicle Required Settings
    vehicle_require_chassis = fields.Boolean(
        string='Require Chassis Number',
        config_parameter='job_card_management.vehicle_require_chassis',
        default=False
    )
    vehicle_require_engine = fields.Boolean(
        string='Require Engine Number',
        config_parameter='job_card_management.vehicle_require_engine',
        default=False
    )
    vehicle_require_year = fields.Boolean(
        string='Require Year of Manufacture',
        config_parameter='job_card_management.vehicle_require_year',
        default=False
    )
    vehicle_require_color = fields.Boolean(
        string='Require Color',
        config_parameter='job_card_management.vehicle_require_color',
        default=False
    )

    # Job Card Settings
    job_card_billing_policy = fields.Selection([
        ('percentage', 'Percentage'),
        ('fixed', 'Fixed Amount')
    ], string="Excess Billing Policy", default='percentage',
       config_parameter='job_card_management.job_card_billing_policy')

    enable_betterment = fields.Boolean(
        string="Enable Betterment",
        config_parameter='job_card_management.enable_betterment',
        default=False
    )

    betterment_billing_policy = fields.Selection([
        ('percentage', 'Percentage'),
        ('fixed', 'Fixed Amount')
    ], string="Betterment Billing Policy", default='percentage',
       config_parameter='job_card_management.betterment_billing_policy')

    @api.model
    def get_values(self):
        res = super(ResConfigSettings, self).get_values()
        res.update(
            job_card_default_terms=self.env['ir.config_parameter'].sudo().get_param('job_card_management.default_terms', default=''),
            purchase_default_terms=self.env['ir.config_parameter'].sudo().get_param('job_card_management.purchase_default_terms', default=''),
            customer_invoice_default_terms=self.env['ir.config_parameter'].sudo().get_param('job_card_management.customer_invoice_default_terms', default=''),
            insurance_invoice_default_terms=self.env['ir.config_parameter'].sudo().get_param('job_card_management.insurance_invoice_default_terms', default=''),
        )
        return res

    def set_values(self):
        super(ResConfigSettings, self).set_values()
        self.env['ir.config_parameter'].sudo().set_param('job_card_management.default_terms', self.job_card_default_terms or '')
        self.env['ir.config_parameter'].sudo().set_param('job_card_management.purchase_default_terms', self.purchase_default_terms or '')
        self.env['ir.config_parameter'].sudo().set_param('job_card_management.customer_invoice_default_terms', self.customer_invoice_default_terms or '')
        self.env['ir.config_parameter'].sudo().set_param('job_card_management.insurance_invoice_default_terms', self.insurance_invoice_default_terms or '')
