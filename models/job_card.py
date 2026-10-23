import logging
import uuid

from odoo.http import request, route as http_route
from odoo.addons.portal.controllers.portal import CustomerPortal

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)

class JobCard(models.Model):
    _name = 'job.card'
    _description = 'Job Card'
    _inherit = ['job.card.backend.navigation.mixin']
    _order = 'id desc'

    def _default_name(self):
        last = self.search([], order='name desc', limit=1)
        if last and last.name and last.name.startswith('JOB-'):
            last_num = int(last.name[4:])  # Get everything after 'JOB-'
            new_num = last_num + 1
        else:
            new_num = 1001  # Starting point

        return f'JOB-{new_num}'  # No zero-padding, just the number

    # def _default_name(self):
    #     random_part = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
    #     return 'JOB-%s-TEX' % random_part

    name = fields.Char(
        string='JOB NO:',
        required=True,
        default=_default_name,
        readonly=True,
        copy=False,
    )
    estimate_id = fields.Many2one('estimate', string='Estimate', required=True, readonly=True)
    customer_id = fields.Many2one('customer', string='First Customer', required=True)
    second_customer_id = fields.Many2one('customer', string='Insurance Company', help='Added at final stage')
    order_number = fields.Char(string='Order NO:')
    claims_number = fields.Char(string='Claims NO:')
    is_insurance = fields.Boolean(string='Insurance', default=True)
    is_cash = fields.Boolean(string='Cash', default=False)
    billing_type = fields.Selection(
        [('insurance', 'Insurance'), ('cash', 'Cash')],
        string='Billing Type',
        default='insurance',
        required=True,
    )
    is_billing_locked = fields.Boolean(
        string='Billing Details Locked',
        default=True,
        copy=False,
        help='Locks billing type after creation/save until Edit button is clicked',
    )
    cash_amount = fields.Float(
        string='Cash AMT',
        compute='_compute_cash_amount',
        store=True,
        readonly=False,
    )
    cash_receipt_ref = fields.Char(string='Receipt No.')
    receipt_attachment = fields.Binary(string='Receipt', attachment=True)
    receipt_filename = fields.Char(string='Receipt Filename')
    excess_percentage = fields.Float(string='Excess (%)', help='Percentage paid by first customer')
    excess_amount = fields.Float(
        string='Excess AMT',
        compute='_compute_excess_amount',
        store=True,
        readonly=False,
    )
    excess_warning_reason = fields.Char(string='Excess Zero Reason', help='Reason why excess amount is 0')
    insurance_percentage = fields.Float(string='Insurance Percentage (%)', compute='_compute_insurance_pct', store=True)
    insurance_amount = fields.Float(
        string='Insurance AMT',
        compute='_compute_insurance_amount',
        store=True,
        readonly=False,
    )

    betterment_percentage = fields.Float(string='Betterment (%)', default=0.0)
    betterment_amount = fields.Float(
        string='Betterment AMT',
        compute='_compute_betterment_amount',
        store=True,
        readonly=False,
        default=0.0,
    )

    billing_policy_setting = fields.Char(
        string='Billing Policy',
        compute='_compute_billing_policy_setting',
    )
    betterment_billing_policy_setting = fields.Char(
        string='Betterment Billing Policy',
        compute='_compute_billing_policy_setting',
    )
    enable_betterment_setting = fields.Boolean(
        string='Betterment Enabled',
        compute='_compute_billing_policy_setting',
    )

    @api.depends_context('uid')
    def _compute_billing_policy_setting(self):
        ICP = self.env['ir.config_parameter'].sudo()
        billing_policy = ICP.get_param('job_card_management.job_card_billing_policy', 'percentage')
        betterment_policy = ICP.get_param('job_card_management.betterment_billing_policy', 'percentage')
        enable_betterment = ICP.get_param('job_card_management.enable_betterment', 'False') == 'True'
        for rec in self:
            rec.billing_policy_setting = billing_policy
            rec.betterment_billing_policy_setting = betterment_policy
            rec.enable_betterment_setting = enable_betterment

    vehicle_id = fields.Many2one(
        'vehicle',
        string='Vehicle',
        required=True,
        domain="['|', ('customer_id', '=', customer_id), ('customer_id', '=', False)]",
    )
    vehicle_reg_number = fields.Char(
        related='vehicle_id.registration_number',
        string='REG NO:',
        readonly=True,
    )
    vehicle_model = fields.Char(related='vehicle_id.model_id.name', string='Vehicle Model', readonly=True)
    vehicle_make = fields.Char(related='vehicle_id.make_id.name', string='Vehicle Make', readonly=True)
    vehicle_display = fields.Char(string='Vehicle', compute='_compute_vehicle_display')
    analytic_account_id = fields.Many2one('account.analytic.account', string='Analytic Account')
    technician_ids = fields.Many2many(
        'job.technician',
        'job_card_technician_rel',
        'job_card_id',
        'technician_id',
        string='Technicians',
    )
    supervisor_ids = fields.Many2many(
        'job.technician',
        'job_card_supervisor_rel',
        'job_card_id',
        'technician_id',
        string='Supervisors',
        domain=[('is_supervisor', '=', True)],
    )
    start_date = fields.Date(string='Start Date Expected', required=True)
    end_date = fields.Date(string='End Date Expected')
    job_card_lines = fields.One2many('job.card.line', 'job_card_id', string='Job Card Lines', copy=True)
    parts_line_ids = fields.One2many(
        'job.card.line', 'parts_job_card_id', string='Supply Parts',
        domain=[('line_category', '=', 'parts')], copy=True
    )
    consumables_line_ids = fields.One2many(
        'job.card.line', 'consumables_job_card_id', string='Consumables',
        domain=[('line_category', '=', 'consumables')], copy=True
    )
    repairs_line_ids = fields.One2many(
        'job.card.line', 'repairs_job_card_id', string='Repair Works',
        domain=[('line_category', '=', 'repairs')], copy=True
    )
    paint_line_ids = fields.One2many(
        'job.card.line', 'paint_job_card_id', string='Paint Job',
        domain=[('line_category', '=', 'paint')], copy=True
    )
    sundries_line_ids = fields.One2many(
        'job.card.line', 'sundries_job_card_id', string='Sundries',
        domain=[('line_category', '=', 'sundries')], copy=True
    )
    fittings_line_ids = fields.One2many(
        'job.card.line', 'fittings_job_card_id', string='Fittings',
        domain=[('line_category', '=', 'fittings')], copy=True
    )
    
    # Invoice tracking fields
    invoice_created = fields.Boolean(string='Invoice Created', default=False)
    customer_invoice_id = fields.Many2one(
        'account.move',
        string='Customer Invoice',
        compute='_compute_linked_invoices',
        store=True,
        readonly=False,
    )
    insurance_invoice_id = fields.Many2one(
        'account.move',
        string='Insurance Invoice',
        compute='_compute_linked_invoices',
        store=True,
        readonly=False,
    )
    auto_create_invoices = fields.Boolean(string='Auto Create Invoices', default=True,
                                          help='Automatically create invoices when job card is created')
    # Split sale orders linked from the estimate
    customer_sale_order_id = fields.Many2one('sale.order', string='Customer Sale Order')
    insurance_sale_order_id = fields.Many2one('sale.order', string='Insurance Sale Order')

    @api.depends('customer_sale_order_id.invoice_ids', 'insurance_sale_order_id.invoice_ids')
    def _compute_linked_invoices(self):
        for rec in self:
            if rec.customer_sale_order_id and rec.customer_sale_order_id.invoice_ids:
                invoices = rec.customer_sale_order_id.invoice_ids.sorted(
                    lambda inv: (inv.state == 'posted', inv.id), reverse=True
                )
                rec.customer_invoice_id = invoices[0].id
            elif not rec.customer_invoice_id:
                rec.customer_invoice_id = False

            if rec.insurance_sale_order_id and rec.insurance_sale_order_id.invoice_ids:
                invoices = rec.insurance_sale_order_id.invoice_ids.sorted(
                    lambda inv: (inv.state == 'posted', inv.id), reverse=True
                )
                rec.insurance_invoice_id = invoices[0].id
            elif not rec.insurance_invoice_id:
                rec.insurance_invoice_id = False
    
    # Add this field
    access_token = fields.Char('Access Token', copy=False)

    # In the JobCard class, replace the _generate_access_token method:
    def _generate_access_token(self):
        """Generate a unique access token for portal access"""
        if not self.access_token:
            self.access_token = str(uuid.uuid4())

    @api.model
    def _get_or_create_service_product(self, name, default_code=None):
        Product = self.env['product.product']
        domain = ['|', ('name', '=ilike', name), ('name', 'ilike', name)]
        if default_code:
            domain = ['|', ('default_code', '=ilike', default_code)] + domain
        prod = Product.search(domain, limit=1)
        if not prod:
            prod = Product.with_context(active_test=False).search(domain, limit=1)
            if prod and not prod.active:
                prod.active = True
        if not prod:
            tmpl_domain = ['|', ('name', '=ilike', name), ('name', 'ilike', name)]
            if default_code:
                tmpl_domain = ['|', ('default_code', '=ilike', default_code)] + tmpl_domain
            tmpl = self.env['product.template'].with_context(active_test=False).search(tmpl_domain, limit=1)
            if tmpl:
                if not tmpl.active:
                    tmpl.active = True
                prod = tmpl.product_variant_id or Product.search([('product_tmpl_id', '=', tmpl.id)], limit=1)
        if not prod:
            vals = {'name': name, 'type': 'service'}
            if default_code:
                vals['default_code'] = default_code
            prod = Product.create(vals)
        return prod

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        
        if self.env.context.get('skip_default_lines'):
            return res
            
        cons_prod = self._get_or_create_service_product('Consumables', default_code='CONS')
        sundries_prod = self._get_or_create_service_product('Sundries', default_code='SUND')

        cons_lines = res.get('consumables_line_ids', [])
        if not cons_lines and cons_prod:
            cons_lines.append((0, 0, {
                'line_category': 'consumables',
                'product_id': cons_prod.id,
                'name': cons_prod.name,
                'quantity': 1.0,
            }))
            res['consumables_line_ids'] = cons_lines

        sundries_lines = res.get('sundries_line_ids', [])
        if not sundries_lines and sundries_prod:
            sundries_lines.append((0, 0, {
                'line_category': 'sundries',
                'product_id': sundries_prod.id,
                'name': sundries_prod.name,
                'quantity': 1.0,
            }))
            res['sundries_line_ids'] = sundries_lines
        
        return res

    def get_portal_url(self, suffix=None, report_type=None):
        """Get the portal URL for this job card"""
        self.ensure_one()
        if not self.access_token:
            self._generate_access_token()
        url = f'/my/jobcards/{self.id}?access_token={self.access_token}'
        if suffix:
            url += f'/{suffix}'
        if report_type:
            url += f'&report_type={report_type}'
        return url

    def _job_card_form_action_xmlid(self):
        return 'job_card_management.action_job_card'

    def _check_schedule_dates(self):
        for rec in self:
            if not rec.start_date:
                raise UserError(_(
                    'Start Date Expected is required before '
                    'saving, confirming, or printing this job card.'
                ))
            if rec.end_date and rec.end_date <= rec.start_date:
                raise UserError(_('End Date Expected must be after Start Date Expected.'))

    def action_preview_job_card(self):
        self._check_schedule_dates()
        report = self.env.ref('job_card_management.report_job_card')
        return {
            'type': 'ir.actions.act_url',
            'url': f'/report/pdf/{report.report_name}/{self.id}',
            'target': 'new',
        }

    def action_preview_portal(self):
        self.ensure_one()
        if not self.access_token:
            self._generate_access_token()
        return {
            'type': 'ir.actions.act_url',
            'url': self.get_portal_url(),
            'target': 'self',
        }

    def action_preview_pick_slip(self):
        self._check_schedule_dates()
        report = self.env.ref('job_card_management.report_job_card_pick_slip')
        return {
            'type': 'ir.actions.act_url',
            'url': f'/report/pdf/{report.report_name}/{self.id}',
            'target': 'new',
        }

    @api.model
    def create(self, vals):
        if isinstance(vals, list):
            for v in vals:
                if not v.get('name') or v.get('name') == 'New':
                    v['name'] = self._default_name()
        else:
            if not vals.get('name') or vals.get('name') == 'New':
                vals['name'] = self._default_name()
        
        # Create the job card
        job_card = super().create(vals)
        
        for rec in job_card:
            # NEW: Fetch and assign analytic account after creation
            analytic_account = rec._fetch_analytic_account()
            if analytic_account:
                rec.analytic_account_id = analytic_account.id
            
            # Check if created from estimate
            is_from_estimate = False
            if isinstance(vals, dict) and vals.get('estimate_id'):
                is_from_estimate = True
            elif rec.estimate_id:
                is_from_estimate = True
                
            if not is_from_estimate:
                # Auto-populate Consumables product line
                if not rec.consumables_line_ids:
                    consumables_product = self._get_or_create_service_product('Consumables', default_code='CONS')
                    if consumables_product:
                        self.env['job.card.line'].create({
                            'job_card_id': rec.id,
                            'consumables_job_card_id': rec.id,
                            'line_category': 'consumables',
                            'product_id': consumables_product.id,
                            'name': consumables_product.name,
                            'quantity': 1.0,
                            'unit_price': 0.0,
                        })
                    
                # Auto-populate Sundries product line
                if not rec.sundries_line_ids:
                    sundries_product = self._get_or_create_service_product('Sundries', default_code='SUND')
                    if sundries_product:
                        self.env['job.card.line'].create({
                            'job_card_id': rec.id,
                            'sundries_job_card_id': rec.id,
                            'line_category': 'sundries',
                            'product_id': sundries_product.id,
                            'name': sundries_product.name,
                            'quantity': 1.0,
                            'unit_price': 0.0,
                        })

        job_card._organize_lines()
        return job_card


    def write(self, vals):
        res = super().write(vals)
        self._organize_lines()
        return res

    def _organize_lines(self):
        categories = ['parts', 'consumables', 'repairs', 'paint', 'sundries', 'fittings']
        from .estimate import LINE_CATEGORY_SELECTION
        category_names = dict(LINE_CATEGORY_SELECTION)
        base_seq = {'parts': 1000, 'consumables': 1500, 'repairs': 2000, 'paint': 3000, 'sundries': 3500, 'fittings': 4000}

        for record in self:
            lines = record.job_card_lines
            for cat in categories:
                cat_lines = lines.filtered(lambda l: l.line_category == cat and not l.display_type)
                cat_notes = lines.filtered(lambda l: l.line_category == cat and l.display_type == 'line_note')
                
                if cat_lines or cat_notes:
                    section = lines.filtered(lambda l: l.line_category == cat and l.display_type == 'line_section')
                    if not section:
                        section = self.env['job.card.line'].create({
                            'job_card_id': record.id,
                            'line_category': cat,
                            'display_type': 'line_section',
                            'name': category_names[cat],
                            'sequence': base_seq[cat]
                        })
                    else:
                        section[0].sequence = base_seq[cat]
                    
                    seq = base_seq[cat] + 1
                    for line in (cat_lines + cat_notes).sorted(key=lambda x: getattr(x, 'id', 0) if isinstance(getattr(x, 'id', 0), int) else 0):
                        line.sequence = seq
                        seq += 1
                else:
                    section = lines.filtered(lambda l: l.line_category == cat and l.display_type == 'line_section')
                    if section:
                        section.unlink()





    # NEW: Method to fetch analytic account
    def _fetch_analytic_account(self):
        """
        Create a new analytic account for this job card using the job card number.
        """
        try:
            # Get the default analytic plan
            try:
                project_plan, _other_plans = self.env['account.analytic.plan']._get_all_plans()
            except UserError:
                # If no project plan is configured, create one or use the first available plan
                project_plan = self.env['account.analytic.plan'].search([], limit=1)
                if not project_plan:
                    project_plan = self.env['account.analytic.plan'].create({'name': 'Default'})
            
            if not project_plan:
                _logger.warning("No analytic plan found. Cannot create analytic account.")
                return None
            
            # Create a new analytic account with the job card name
            analytic_account = self.env['account.analytic.account'].create({
                'name': self.name,
                'plan_id': project_plan.id,
            })
            
            return analytic_account
        except Exception as e:
            _logger.error(f"Error creating analytic account for job card {self.name}: {str(e)}")
            return None

    # NEW: Method to create invoices
    def _create_invoices(self):
        """Create invoices for both customer and insurance"""
        if self.invoice_created:
            return False
        
        if not self.second_customer_id:
            raise UserError(_('Please add Insurance Company as Second Customer before creating invoices.'))
        if not self.excess_percentage:
            raise UserError(_('Please set the Excess percentage.'))
        
        # Find income account
        income_account = self.env['account.account'].search([('account_type', '=', 'income')], limit=1)
        if not income_account:
            raise UserError(_('No income account configured. Please set up an income account in Accounting.'))
        
        # Get current date for invoice
        invoice_date = fields.Date.today()
        
        # Create invoice for customer (excess / betterment amount)
        if (self.excess_amount > 0 or self.betterment_amount > 0) and self.customer_id and self.customer_id.partner_id:
            customer_terms = self.env['ir.config_parameter'].sudo().get_param('job_card_management.customer_invoice_default_terms', default='')
            narration = customer_terms if customer_terms else f"Customer portion (Excess) of Job Card {self.name}"
            
            excess_product = self._get_or_create_service_product('Excess')
            betterment_product = self._get_or_create_service_product('Betterment')
            
            customer_invoice_lines = []
            if self.excess_amount > 0:
                customer_invoice_lines.append((0, 0, {
                    'product_id': excess_product.id,
                    'name': excess_product.name,
                    'quantity': 1.0,
                    'price_unit': self.excess_amount,
                    'account_id': income_account.id,
                }))
            if self.enable_betterment_setting and self.betterment_amount > 0:
                customer_invoice_lines.append((0, 0, {
                    'product_id': betterment_product.id,
                    'name': betterment_product.name,
                    'quantity': 1.0,
                    'price_unit': self.betterment_amount,
                    'account_id': income_account.id,
                }))
            
            if customer_invoice_lines:
                customer_invoice = self.env['account.move'].create({
                    'move_type': 'out_invoice',
                    'partner_id': self.customer_id.partner_id.id,
                    'invoice_origin': self.name,
                    'invoice_line_ids': customer_invoice_lines,
                    'invoice_date': invoice_date,
                    'narration': narration,
                    'ref': f"Job Card: {self.name} - Customer Portion (Excess)",
                })
                customer_invoice.action_post()
                self.customer_invoice_id = customer_invoice.id
        
        # Create invoice for insurance (full quoted items at 100% price)
        insurance_lines = self._prepare_invoice_lines('insurance', income_account)
        if insurance_lines and self.second_customer_id and self.second_customer_id.partner_id:
            insurance_terms = self.env['ir.config_parameter'].sudo().get_param('job_card_management.insurance_invoice_default_terms', default='')
            narration = insurance_terms if insurance_terms else f"Insurance portion of Job Card {self.name}"
            
            insurance_invoice = self.env['account.move'].create({
                'move_type': 'out_invoice',
                'is_insurance_invoice': True,
                'partner_id': self.second_customer_id.partner_id.id,
                'invoice_origin': self.name,
                'invoice_line_ids': insurance_lines,
                'invoice_date': invoice_date,
                'narration': narration,
                'ref': f"Job Card: {self.name} - Insurance Portion",
            })
            insurance_invoice.action_post()
            self.insurance_invoice_id = insurance_invoice.id
        
        self.invoice_created = True
        return True

    # NEW: Helper method to prepare invoice lines
    def _prepare_invoice_lines(self, invoice_type, income_account):
        """Prepare invoice lines for insurance or full quote, including sections and exact unit prices"""
        lines = []
        
        for line in self.job_card_lines:
            # Include section headers and notes as-is
            if line.display_type:
                invoice_line_vals = {
                    'display_type': line.display_type,
                    'name': line.name,
                }
                lines.append((0, 0, invoice_line_vals))
            # Include product lines with exact unit prices (no excess discount)
            elif line.price_total > 0 or line.unit_price > 0:
                price_unit = line.unit_price
                invoice_line_vals = {
                    'name': line.name or (line.product_id.name if line.product_id else 'Job Card Service'),
                    'quantity': line.quantity,
                    'price_unit': price_unit,
                    'discount': line.discount or 0.0,
                    'account_id': income_account.id,
                }
                if line.product_id:
                    invoice_line_vals['product_id'] = line.product_id.id
                if line.tax_ids:
                    invoice_line_vals['tax_ids'] = [(6, 0, line.tax_ids.ids)]
                # Assign analytic account to invoice line if available
                if self.analytic_account_id:
                    invoice_line_vals['analytic_distribution'] = {
                        str(self.analytic_account_id.id): 100.0
                    }
                
                lines.append((0, 0, invoice_line_vals))
        
        return lines
    inventory_issue_ids = fields.One2many('job.inventory.issue', 'job_card_id', string='Inventory Issues')
    inventory_issue_count = fields.Integer(string='Inventory Issues Count', compute='_compute_inventory_issue_count')
    all_inventory_issued = fields.Boolean(string='All Inventory Issued', compute='_compute_all_inventory_issued', store=True)

    consumable_issue_ids = fields.One2many('job.consumable.issue', 'job_card_id', string='Consumable Issues')
    consumable_issue_count = fields.Integer(string='Consumable Issues Count', compute='_compute_consumable_issue_count')
    all_consumables_issued = fields.Boolean(string='All Consumables Issued', tracking=True, default=False)

    @api.depends('consumable_issue_ids', 'consumable_issue_ids.state')
    def _compute_consumable_issue_count(self):
        for rec in self:
            rec.consumable_issue_count = len(rec.consumable_issue_ids.filtered(lambda i: i.state == 'issued'))

    @api.depends('inventory_issue_ids', 'inventory_issue_ids.state')
    def _compute_inventory_issue_count(self):
        for rec in self:
            rec.inventory_issue_count = len(rec.inventory_issue_ids.filtered(lambda i: i.state == 'issued'))

    @api.depends('parts_line_ids', 'parts_line_ids.quantity', 'parts_line_ids.product_id',
                 'inventory_issue_ids.state', 'inventory_issue_ids.issue_line_ids.issued_qty')
    def _compute_all_inventory_issued(self):
        for rec in self:
            # Only Supply Parts (parts_line_ids) are considered for inventory issue tracking
            all_lines = rec.parts_line_ids.filtered(
                lambda l: not l.display_type and l.product_id
            ).filtered(lambda l: l.product_id.type in ('product', 'consu'))
                
            if not all_lines:
                rec.all_inventory_issued = True
                continue

            active_issues = rec.inventory_issue_ids.filtered(lambda i: i.state in ('issued', 'partially_issued'))
            completed_procurements = self.env['procurement'].search([
                ('job_card_id', '=', rec.id),
                ('state', '=', 'purchase_order_created')
            ])

            all_issued = True
            for product in all_lines.mapped('product_id'):
                required_qty = sum(all_lines.filtered(lambda l: l.product_id == product).mapped('quantity'))
                issued_qty = sum(
                    active_issues.mapped('issue_line_ids')
                    .filtered(lambda il: il.product_id == product)
                    .mapped('issued_qty')
                )
                
                # Only count internal transfers that have actually been marked delivered
                delivered_transfer_qty = sum(
                    completed_procurements.mapped('procurement_lines')
                    .filtered(lambda pl: pl.type == 'internal_transfer' and pl.receipt_status == 'delivered' and pl.product_id.id == product.id)
                    .mapped('quantity')
                )
                issued_qty += delivered_transfer_qty
                
                if issued_qty < required_qty:
                    all_issued = False
                    break
                    
            rec.all_inventory_issued = all_issued

    def action_issue_inventory(self):
        self.ensure_one()
        # Only Supply Parts lines are eligible for inventory issue
        all_lines = self.parts_line_ids.filtered(
            lambda l: l.display_type not in ('line_section', 'line_note') and l.product_id
        )
        if not all_lines:
            raise UserError(_('There are no Supply Parts lines to issue for this job card.'))

        existing = self.inventory_issue_ids.filtered(lambda i: i.state in ('draft', 'confirmed', 'partially_issued'))[:1]
        if existing:
            existing._onchange_source_location()
            return {
                'type': 'ir.actions.act_window',
                'name': _('Issue Inventory'),
                'res_model': 'job.inventory.issue',
                'res_id': existing.id,
                'view_mode': 'form',
                'target': 'current',
            }

        issue = self.env['job.inventory.issue'].create({
            'job_card_id': self.id,
        })
        issue.action_populate_from_job_card()
            
        return {
            'type': 'ir.actions.act_window',
            'name': _('Issue Inventory'),
            'res_model': 'job.inventory.issue',
            'res_id': issue.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def action_issue_consumables(self):
        self.ensure_one()
        all_lines = (
            self.consumables_line_ids |
            self.paint_line_ids |
            self.sundries_line_ids |
            self.parts_line_ids
        ).filtered(lambda l: l.display_type not in ('line_section', 'line_note') and l.product_id)
        if not all_lines:
            raise UserError(_('There are no consumable lines to issue.'))

        issue = self.env['job.consumable.issue'].create({
            'job_card_id': self.id,
        })
        issue.action_populate_from_job_card()
            
        return {
            'type': 'ir.actions.act_window',
            'name': _('Issue Consumables'),
            'res_model': 'job.consumable.issue',
            'res_id': issue.id,
            'view_mode': 'form',
            'target': 'current',
        }
            
    state = fields.Selection([
        ('draft', 'Draft'),
        ('approved', 'Approved'),
        ('pending_inventory', 'Pending Inventory Issue'),
        ('inventory_issued', 'Inventory Issued'),
        ('pending_items', 'Pending Items'),
        ('in_progress', 'In Progress'),
        ('requisition_started', 'Requisition Started'),
        ('completed', 'Completed'),
        ('delivered', 'Delivered')
    ], default='draft')
    total_amount = fields.Float(string='Total Amount', compute='_compute_total', store=True)

    payment_state = fields.Selection([
        ('not_paid', 'Not Paid'),
        ('in_payment', 'In Payment'),
        ('paid', 'Paid'),
        ('partial', 'Partially Paid'),
        ('reversed', 'Reversed'),
        ('invoicing_legacy', 'Invoicing App Legacy'),
    ], string='Payment Status', tracking=True, default='not_paid')
    
    authorization_type = fields.Selection([
        ('file', 'File'),
        ('link', 'Link')
    ], string='Authorization Type', default='file')
    authorization_letter = fields.Binary(string='Authorization Letter')
    authorization_letter_filename = fields.Char(string='Authorization Letter Filename')
    authorization_link = fields.Char(string='Authorization Link')


    amount_untaxed = fields.Float(string='Total Excl', compute='_compute_total', store=True)
    amount_tax = fields.Float(string='Total Tax', compute='_compute_total', store=True)
    amount_total = fields.Float(string='Total Incl', compute='_compute_total', store=True)

    job_cost_count = fields.Integer(string='Job Cost', compute='_compute_job_cost_count')
    job_cost_total = fields.Float(string='Job Cost Total', compute='_compute_job_cost_count')

    def _compute_job_cost_count(self):
        JobCost = self.env['job.cost']
        for rec in self:
            cost = JobCost.search([('job_card_id', '=', rec.id)], limit=1)
            rec.job_cost_count = 1 if cost else 0
            
            # Dynamically compute the expected total cost so it's always up-to-date on the smart button
            total = 0.0
            for line in rec.job_card_lines.filtered(lambda l: not l.display_type):
                cost_price = JobCost._get_latest_cost(line.product_id)
                total += line.quantity * cost_price
                
            issued_consumables = rec.consumable_issue_ids.filtered(lambda i: i.state == 'issued')
            for issue in issued_consumables:
                for issue_line in issue.issue_line_ids.filtered(lambda l: l.issued_qty > 0):
                    cost_price = issue_line.product_id.standard_price
                    total += issue_line.issued_qty * cost_price
                    
            rec.job_cost_total = total

    def action_view_inventory_issues(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Inventory Issues'),
            'res_model': 'job.inventory.issue',
            'view_mode': 'list,form',
            'domain': [('job_card_id', '=', self.id)],
            'context': {'default_job_card_id': self.id},
        }

    def action_view_consumables_issues(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Consumable Issues'),
            'res_model': 'job.consumable.issue.line',
            'view_mode': 'list,form',
            'domain': [('issue_id.job_card_id', '=', self.id), ('issue_id.state', '=', 'issued')],
        }

    def action_view_job_cost(self):
        self.ensure_one()
        cost = self.env['job.cost'].search([('job_card_id', '=', self.id)], limit=1)
        if not cost:
            cost = self.env['job.cost'].create({'job_card_id': self.id})
        cost.compute_costs()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Job Cost'),
            'res_model': 'job.cost',
            'res_id': cost.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def action_reopen(self):
        """Reopen / edit a job card to allow changing details"""
        if not self.env.user.has_group('job_card_management.group_can_reopen_job_card'):
            raise UserError(_('You do not have permission to reopen job cards. Please contact your administrator.'))
        
        for rec in self:
            if rec.estimate_id and rec.estimate_id.sale_order_id:
                sale_order = rec.estimate_id.sale_order_id
                if sale_order.state not in ('cancel', 'done'):
                    sale_order.action_cancel()
            rec.with_context(skip_billing_lock=True).write({
                'is_billing_locked': False,
                'state': 'draft',
            })

    def action_unlock_billing(self):
        """Unlock billing type radio selection for editing"""
        for rec in self:
            rec.is_billing_locked = False

    @api.depends('amount_total', 'is_cash')
    def _compute_cash_amount(self):
        for rec in self:
            if rec.is_cash:
                rec.cash_amount = rec.amount_total
            else:
                rec.cash_amount = 0.0

    @api.onchange('second_customer_id')
    def _onchange_second_customer_id(self):
        if self.second_customer_id:
            if not self.insurance_amount:
                self.insurance_amount = self.amount_total
            self.insurance_percentage = 100.0
        else:
            self.insurance_amount = 0.0
            self.insurance_percentage = 0.0

    @api.depends('amount_total', 'second_customer_id')
    def _compute_insurance_amount(self):
        for rec in self:
            if rec.second_customer_id:
                rec.insurance_amount = rec.amount_total
            else:
                rec.insurance_amount = 0.0

    @api.depends('amount_total', 'excess_percentage')
    def _compute_excess_amount(self):
        for rec in self:
            if rec.excess_percentage and rec.amount_total:
                rec.excess_amount = (rec.excess_percentage / 100.0) * rec.amount_total
            elif not rec.excess_amount:
                rec.excess_amount = 0.0

    @api.depends('amount_total', 'betterment_percentage')
    def _compute_betterment_amount(self):
        for rec in self:
            if rec.betterment_percentage and rec.amount_total:
                rec.betterment_amount = (rec.betterment_percentage / 100.0) * rec.amount_total
            elif not rec.betterment_amount:
                rec.betterment_amount = 0.0

    @api.depends('insurance_amount', 'amount_total', 'second_customer_id')
    def _compute_insurance_pct(self):
        for rec in self:
            if not rec.second_customer_id:
                rec.insurance_percentage = 0.0
            elif rec.amount_total > 0 and rec.insurance_amount:
                rec.insurance_percentage = (rec.insurance_amount / rec.amount_total) * 100.0
            elif rec.amount_total > 0 and rec.second_customer_id:
                rec.insurance_percentage = 100.0
            else:
                rec.insurance_percentage = 0.0

    @api.onchange('excess_percentage')
    def _onchange_excess_percentage(self):
        if self.excess_percentage and self.amount_total:
            self.excess_amount = (self.excess_percentage / 100.0) * self.amount_total

    @api.onchange('billing_type')
    def _onchange_billing_type(self):
        if self.billing_type == 'insurance':
            self.is_insurance = True
            self.is_cash = False
            if not self.second_customer_id and self.estimate_id and self.estimate_id.insurance_company_id:
                self.second_customer_id = self.estimate_id.insurance_company_id.id
        elif self.billing_type == 'cash':
            self.is_insurance = False
            self.is_cash = True
            self.cash_amount = self.amount_total
            self.second_customer_id = False
            self.excess_percentage = 0.0
            self.excess_amount = 0.0
            self.betterment_percentage = 0.0
            self.betterment_amount = 0.0
            self.insurance_amount = 0.0
            self.insurance_percentage = 0.0
            self.order_number = False
            self.claims_number = False

    @api.onchange('is_insurance')
    def _onchange_is_insurance(self):
        if self.is_insurance:
            self.is_cash = False
            self.billing_type = 'insurance'
            if not self.second_customer_id and self.estimate_id and self.estimate_id.insurance_company_id:
                self.second_customer_id = self.estimate_id.insurance_company_id.id
        elif not self.is_cash:
            self.is_cash = True
            self.billing_type = 'cash'

    @api.onchange('is_cash')
    def _onchange_is_cash(self):
        if self.is_cash:
            self.is_insurance = False
            self.billing_type = 'cash'
            self.cash_amount = self.amount_total
            self.second_customer_id = False
            self.excess_percentage = 0.0
            self.excess_amount = 0.0
            self.betterment_percentage = 0.0
            self.betterment_amount = 0.0
            self.insurance_amount = 0.0
            self.insurance_percentage = 0.0
            self.order_number = False
            self.claims_number = False
        elif not self.is_insurance:
            self.is_insurance = True
            self.billing_type = 'insurance'

    @api.onchange('betterment_percentage')
    def _onchange_betterment_percentage(self):
        if self.betterment_percentage and self.amount_total:
            self.betterment_amount = (self.betterment_percentage / 100.0) * self.amount_total

    @api.onchange('excess_amount', 'betterment_amount', 'amount_total')
    def _onchange_financial_amounts(self):
        if self.amount_total > 0:
            if self.excess_amount:
                self.excess_percentage = (self.excess_amount / self.amount_total) * 100.0
            if self.betterment_amount:
                self.betterment_percentage = (self.betterment_amount / self.amount_total) * 100.0
            if self.second_customer_id:
                if not self.insurance_amount:
                    self.insurance_amount = self.amount_total
                self.insurance_percentage = (self.insurance_amount / self.amount_total) * 100.0

    @api.depends('vehicle_id', 'vehicle_id.registration_number', 'vehicle_id.make_id.name', 'vehicle_id.model_id.name')
    def _compute_vehicle_display(self):
        for rec in self:
            if rec.vehicle_id:
                reg = rec.vehicle_id.registration_number or ''
                make_model = ' '.join(
                    p for p in [rec.vehicle_id.make_id.name, rec.vehicle_id.model_id.name] if p
                )
                rec.vehicle_display = f"[{reg}] {make_model}".strip()
            else:
                rec.vehicle_display = ""


    @api.constrains('authorization_letter_filename')
    def _check_authorization_file_extension(self):
        for rec in self:
            if rec.authorization_letter_filename:
                allowed_extensions = ('.pdf', '.txt', '.doc', '.docx')
                if not rec.authorization_letter_filename.lower().endswith(allowed_extensions):
                    raise ValidationError("The authorization letter must be a PDF, TXT, DOC, or DOCX file.")


    @api.constrains('excess_amount', 'betterment_amount', 'amount_total', 'is_insurance')
    def _check_insurance_amounts(self):
        for rec in self:
            if rec.is_insurance:
                if rec.excess_amount < 0 or rec.betterment_amount < 0:
                    raise ValidationError("Excess and Betterment amounts must be positive.")
                if round(rec.excess_amount + rec.betterment_amount, 2) > round(rec.amount_total, 2):
                    raise ValidationError("The sum of Excess and Betterment amounts cannot exceed the Total Invoice amount.")

    @api.depends(
        'job_card_lines.price_total', 'job_card_lines.price_subtotal', 'job_card_lines.tax_amount',
        'parts_line_ids.price_subtotal', 'parts_line_ids.price_total', 'parts_line_ids.tax_amount',
        'consumables_line_ids.price_subtotal', 'consumables_line_ids.price_total', 'consumables_line_ids.tax_amount',
        'repairs_line_ids.price_subtotal', 'repairs_line_ids.price_total', 'repairs_line_ids.tax_amount',
        'paint_line_ids.price_subtotal', 'paint_line_ids.price_total', 'paint_line_ids.tax_amount',
        'sundries_line_ids.price_subtotal', 'sundries_line_ids.price_total', 'sundries_line_ids.tax_amount',
        'fittings_line_ids.price_subtotal', 'fittings_line_ids.price_total', 'fittings_line_ids.tax_amount'
    )
    def _compute_total(self):
        import logging
        _logger = logging.getLogger(__name__)
        for rec in self:
            all_lines = rec.job_card_lines | rec.parts_line_ids | rec.consumables_line_ids | rec.repairs_line_ids | rec.paint_line_ids | rec.sundries_line_ids | rec.fittings_line_ids
            lines = all_lines.filtered(lambda l: not l.display_type)
            _logger.info("COMPUTE TOTAL CALLED! parts: %s, all: %s", len(rec.parts_line_ids), len(all_lines))
            for l in lines:
                _logger.info("LINE ID: %s, subtotal: %s", l.id, l.price_subtotal)
            rec.amount_untaxed = sum(lines.mapped('price_subtotal'))
            rec.amount_tax = sum(lines.mapped('tax_amount'))
            rec.amount_total = rec.amount_untaxed + rec.amount_tax
            rec.total_amount = rec.insurance_amount if (rec.is_insurance and rec.second_customer_id and rec.insurance_amount) else rec.amount_total
            if rec.is_insurance:
                if rec.second_customer_id and (not rec.insurance_amount or rec.insurance_amount == 0.0):
                    rec.insurance_amount = rec.amount_total
                if rec.excess_percentage and (not rec.excess_amount or rec.excess_amount == 0.0):
                    rec.excess_amount = (rec.excess_percentage / 100.0) * rec.amount_total
                if rec.betterment_percentage and (not rec.betterment_amount or rec.betterment_amount == 0.0):
                    rec.betterment_amount = (rec.betterment_percentage / 100.0) * rec.amount_total
            elif rec.is_cash:
                if not rec.cash_amount or rec.cash_amount == 0.0:
                    rec.cash_amount = rec.amount_total

    def _organize_sections(self):
        categories = ['parts', 'consumables', 'repairs', 'paint', 'sundries', 'fittings']
        from .estimate import LINE_CATEGORY_SELECTION
        category_names = dict(LINE_CATEGORY_SELECTION)
        base_seq = {'parts': 1000, 'consumables': 1500, 'repairs': 2000, 'paint': 3000, 'sundries': 3500, 'fittings': 4000}
        
        for rec in self:
            for cat in categories:
                # Get lines from the specific category tab
                cat_lines = getattr(rec, f'{cat}_line_ids').filtered(lambda l: l.display_type != 'line_section')
                if cat_lines:
                    # Link them to the main order lines
                    for line in cat_lines:
                        line.job_card_id = rec.id

                    section = rec.job_card_lines.filtered(lambda l: l.line_category == cat and l.display_type == 'line_section')
                    if not section:
                        self.env['job.card.line'].create({
                            'job_card_id': rec.id,
                            'line_category': cat,
                            'display_type': 'line_section',
                            'name': category_names[cat],
                            'sequence': base_seq[cat]
                        })
                    else:
                        section.sequence = base_seq[cat]
                    
                    seq = base_seq[cat] + 1
                    for line in cat_lines:
                        line.sequence = seq
                        seq += 1

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if 'billing_type' in vals:
                if vals['billing_type'] == 'cash':
                    vals['is_cash'] = True
                    vals['is_insurance'] = False
                elif vals['billing_type'] == 'insurance':
                    vals['is_insurance'] = True
                    vals['is_cash'] = False
            elif 'is_cash' in vals and not vals.get('is_insurance'):
                vals['billing_type'] = 'cash' if vals['is_cash'] else 'insurance'
            elif 'is_insurance' in vals and not vals.get('is_cash'):
                vals['billing_type'] = 'insurance' if vals['is_insurance'] else 'cash'
        records = super().create(vals_list)
        records._organize_sections()
        for rec in records:
            if rec.is_insurance:
                vals_to_write = {}
                if rec.second_customer_id and not rec.insurance_amount and rec.amount_total:
                    vals_to_write['insurance_amount'] = rec.amount_total
                if rec.excess_percentage and not rec.excess_amount and rec.amount_total:
                    vals_to_write['excess_amount'] = (rec.excess_percentage / 100.0) * rec.amount_total
                if rec.betterment_percentage and not rec.betterment_amount and rec.amount_total:
                    vals_to_write['betterment_amount'] = (rec.betterment_percentage / 100.0) * rec.amount_total
                if vals_to_write:
                    rec.write(vals_to_write)
        return records

    def write(self, vals):
        if 'billing_type' in vals:
            if vals['billing_type'] == 'cash':
                vals['is_cash'] = True
                vals['is_insurance'] = False
            elif vals['billing_type'] == 'insurance':
                vals['is_insurance'] = True
                vals['is_cash'] = False
        elif 'is_cash' in vals and 'is_insurance' not in vals:
            vals['is_insurance'] = not vals['is_cash']
            vals['billing_type'] = 'cash' if vals['is_cash'] else 'insurance'
        elif 'is_insurance' in vals and 'is_cash' not in vals:
            vals['is_cash'] = not vals['is_insurance']
            vals['billing_type'] = 'insurance' if vals['is_insurance'] else 'cash'

        if 'is_billing_locked' not in vals and not self.env.context.get('skip_billing_lock'):
            # Only relock when user saves with billing fields changed or if it was already locked
            for rec in self:
                b_type = vals.get('billing_type', rec.billing_type)
                sec_cust = vals.get('second_customer_id', rec.second_customer_id.id if rec.second_customer_id else False)
                cash_ref = vals.get('cash_receipt_ref', rec.cash_receipt_ref)
                cash_att = vals.get('receipt_attachment', rec.receipt_attachment)
                # If editing billing type or saving customer details, lock upon save
                if ('billing_type' in vals or 'second_customer_id' in vals or 'cash_receipt_ref' in vals or 'receipt_attachment' in vals or rec.is_billing_locked):
                    if (b_type == 'insurance' and sec_cust) or (b_type == 'cash' and (cash_ref or cash_att)):
                        vals['is_billing_locked'] = True

        res = super().write(vals)
        self._organize_sections()
        if not self.env.context.get('skip_financial_auto_write'):
            for rec in self.with_context(skip_financial_auto_write=True):
                if rec.is_insurance:
                    vals_to_write = {}
                    if rec.second_customer_id and not rec.insurance_amount and rec.amount_total:
                        vals_to_write['insurance_amount'] = rec.amount_total
                    if rec.excess_percentage and not rec.excess_amount and rec.amount_total:
                        vals_to_write['excess_amount'] = (rec.excess_percentage / 100.0) * rec.amount_total
                    if rec.betterment_percentage and not rec.betterment_amount and rec.amount_total:
                        vals_to_write['betterment_amount'] = (rec.betterment_percentage / 100.0) * rec.amount_total
                    if vals_to_write:
                        rec.write(vals_to_write)
        return res

    def _build_so_lines_from_job(self, price_multiplier=1.0):
        """Build sale order lines from job card lines, applying a price multiplier for splits."""
        lines = []
        for line in self.job_card_lines:
            line_vals = {}
            if line.display_type:
                line_vals['display_type'] = line.display_type
                line_vals['name'] = line.name
            else:
                line_vals['name'] = line.name or (line.product_id.name if line.product_id else '')
                line_vals['product_uom_qty'] = line.quantity
                line_vals['price_unit'] = line.unit_price * price_multiplier
                if line.product_id:
                    line_vals['product_id'] = line.product_id.id
                if line.product_uom_id:
                    line_vals['product_uom_id'] = line.product_uom_id.id
                if line.tax_ids:
                    line_vals['tax_ids'] = [(6, 0, line.tax_ids.ids)]
                if line.discount:
                    line_vals['discount'] = line.discount
                if self.analytic_account_id:
                    line_vals['analytic_distribution'] = {str(self.analytic_account_id.id): 100.0}
            lines.append(line_vals)
        return lines

    def action_approve_job_card(self):
        for rec in self:
            vals_to_fix = {}
            if rec.is_insurance:
                if not rec.excess_amount and rec.excess_percentage and rec.amount_total:
                    vals_to_fix['excess_amount'] = (rec.excess_percentage / 100.0) * rec.amount_total
                if not rec.insurance_amount and rec.second_customer_id:
                    vals_to_fix['insurance_amount'] = rec.amount_total
                if vals_to_fix:
                    rec.with_context(skip_financial_auto_write=True).write(vals_to_fix)

                excess_amt = rec.excess_amount or vals_to_fix.get('excess_amount', 0.0)
                # Soft excess warning: if insurance is checked and excess is 0
                if not excess_amt and not rec.excess_warning_reason:
                    return {
                        'type': 'ir.actions.act_window',
                        'name': 'Excess Amount Warning',
                        'res_model': 'job.card.excess.warning.wizard',
                        'view_mode': 'form',
                        'target': 'new',
                        'context': {
                            'default_job_card_id': rec.id,
                        }
                    }

            rec.state = 'pending_inventory'
            if not rec.access_token:
                rec._generate_access_token()

            # Create Sales Orders if not already created
            if not rec.customer_sale_order_id:
                has_insurance = bool(
                    rec.is_insurance and
                    rec.second_customer_id and
                    rec.second_customer_id.partner_id
                )
                
                # Fetch settings
                billing_policy = self.env['ir.config_parameter'].sudo().get_param('job_card_management.job_card_billing_policy', 'percentage')
                enable_betterment = self.env['ir.config_parameter'].sudo().get_param('job_card_management.enable_betterment', 'False') == 'True'
                betterment_policy = self.env['ir.config_parameter'].sudo().get_param('job_card_management.betterment_billing_policy', 'percentage')

                excess_product = self._get_or_create_service_product('Excess')
                betterment_product = self._get_or_create_service_product('Betterment')

                # Total Job Card Amount for percentage calculations
                total_amount = rec.amount_total

                if has_insurance:
                    # Prefer exact manual amounts entered by user
                    excess_value = rec.excess_amount
                    if not excess_value and rec.excess_percentage and total_amount:
                        excess_value = total_amount * (rec.excess_percentage / 100.0)

                    if enable_betterment:
                        betterment_value = rec.betterment_amount
                        if not betterment_value and rec.betterment_percentage and total_amount:
                            betterment_value = total_amount * (rec.betterment_percentage / 100.0)
                    else:
                        betterment_value = 0.0

                    insurance_value = total_amount

                    # Customer SO (Excess / Betterment)
                    customer_so = self.env['sale.order'].create({
                        'partner_id': rec.customer_id.partner_id.id,
                        'user_id': self.env.user.id,
                        'origin': f"{rec.name} (Customer)",
                        'note': f"Customer portion (Excess) of Job Card {rec.name}",
                    })
                    rec.customer_sale_order_id = customer_so.id
                    
                    # Create Excess Line
                    self.env['sale.order.line'].create({
                        'order_id': customer_so.id,
                        'product_id': excess_product.id,
                        'name': excess_product.name,
                        'product_uom_qty': 1.0,
                        'price_unit': excess_value,
                    })
                    
                    # Create Betterment Line if > 0
                    if enable_betterment and betterment_value > 0:
                        self.env['sale.order.line'].create({
                            'order_id': customer_so.id,
                            'product_id': betterment_product.id,
                            'name': betterment_product.name,
                            'product_uom_qty': 1.0,
                            'price_unit': betterment_value,
                        })
                        
                    customer_so.action_confirm()

                    # Insurance SO: full quote lines at 100% unit prices (multiplier 1.0)
                    insurance_so = self.env['sale.order'].create({
                        'partner_id': rec.second_customer_id.partner_id.id,
                        'user_id': customer_so.user_id.id or self.env.user.id,
                        'origin': f"{rec.name} (Insurance)",
                        'note': f"Insurance portion of Job Card {rec.name}",
                    })
                    rec.insurance_sale_order_id = insurance_so.id
                    for line_vals in rec._build_so_lines_from_job(price_multiplier=1.0):
                        self.env['sale.order.line'].create(dict(line_vals, order_id=insurance_so.id))
                    insurance_so.action_confirm()
                else:
                    # Cash / Customer-only: single SO for customer, full quote lines
                    sale_order = self.env['sale.order'].create({
                        'partner_id': rec.customer_id.partner_id.id,
                        'user_id': self.env.user.id,
                        'origin': rec.name,
                        'note': f"Job Card {rec.name} (Cash Payment)",
                    })
                    rec.customer_sale_order_id = sale_order.id
                    for line_vals in rec._build_so_lines_from_job(price_multiplier=1.0):
                        self.env['sale.order.line'].create(dict(line_vals, order_id=sale_order.id))
                    sale_order.action_confirm()
            
            # Auto-create invoices if enabled
            if rec.auto_create_invoices:
                try:
                    rec._generate_linked_invoices()
                except UserError as e:
                    _logger.warning(f"Could not auto-create invoices for job card {rec.name}: {str(e)}")
        return True

    def action_start_job(self):
        self._check_schedule_dates()
        self.state = 'in_progress'
        return True

    def action_create_requisition(self):
        if self.state in ['completed', 'delivered']:
            raise UserError(_('You cannot create a requisition for a completed job.'))
        self._check_schedule_dates()
        
        if not self.analytic_account_id:
            self.analytic_account_id = self._fetch_analytic_account()
        
        procurement = self.env['procurement'].create({
            'job_card_id': self.id,
            'analytic_account_id': self.analytic_account_id.id if self.analytic_account_id else False,
        })
        # Create procurement lines from supply parts lines only
        for line in self.parts_line_ids:
            if line.display_type:
                self.env['procurement.line'].create({
                    'procurement_id': procurement.id,
                    'sequence': line.sequence,
                    'display_type': line.display_type,
                    'name': line.name,
                    'type': 'purchase_order',
                    'quantity': 0.0,
                })
            elif line.product_id:
                self.env['procurement.line'].create({
                    'procurement_id': procurement.id,
                    'sequence': line.sequence,
                    'product_id': line.product_id.id,
                    'product_uom_id': line.product_uom_id.id if line.product_uom_id else False,
                    'quantity': line.quantity,
                    'buying_price': line.product_id.standard_price or 0.0,
                    'selling_price': line.unit_price or line.product_id.lst_price or 0.0,
                    'type': 'purchase_order',
                })
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'procurement',
            'res_id': procurement.id,
            'view_mode': 'form',
        }

    def _generate_linked_invoices(self):
        """Generate invoices from linked SOs or standalone."""
        if self.invoice_created:
            return

        if self.customer_sale_order_id:
            # Invoice customer SO
            if not self.customer_sale_order_id.invoice_ids and self.customer_sale_order_id.invoice_status in ('to invoice', 'no'):
                customer_invoices = self.customer_sale_order_id._create_invoices()
                if customer_invoices:
                    self.customer_invoice_id = customer_invoices[0].id
                    try:
                        customer_invoices.action_post()
                    except Exception as e:
                        _logger.warning(f"Could not auto-post customer invoice for job card {self.name}: {e}")
            elif self.customer_sale_order_id.invoice_ids:
                self.customer_invoice_id = self.customer_sale_order_id.invoice_ids[0].id

        if self.is_insurance and self.insurance_sale_order_id:
            # Invoice insurance SO (if exists)
            if not self.insurance_sale_order_id.invoice_ids and self.insurance_sale_order_id.invoice_status in ('to invoice', 'no'):
                insurance_invoices = self.insurance_sale_order_id._create_invoices()
                if insurance_invoices:
                    self.insurance_invoice_id = insurance_invoices[0].id
                    insurance_invoices.write({'is_insurance_invoice': True})
                    try:
                        insurance_invoices.action_post()
                    except Exception as e:
                        _logger.warning(f"Could not auto-post insurance invoice for job card {self.name}: {e}")
            elif self.insurance_sale_order_id.invoice_ids:
                self.insurance_invoice_id = self.insurance_sale_order_id.invoice_ids[0].id

        self.invoice_created = bool(self.customer_invoice_id or (self.is_insurance and self.insurance_invoice_id))

    def action_finalize_job_card(self):
        if self.is_insurance:
            if not self.second_customer_id:
                raise UserError(_('Please add Insurance Company as Second Customer before finalizing.'))
            if not self.excess_percentage and self.billing_policy_setting == 'percentage' and not self.excess_warning_reason:
                raise UserError(_('Please set the Excess percentage or provide a reason why excess is zero.'))
        if not self.all_inventory_issued:
            raise UserError(_('You cannot finalize the job until all parts have been issued or requisitioned.'))
        if self.consumables_line_ids and not self.all_consumables_issued:
            raise UserError(_('You cannot finalize the job until all Consumables have been issued.'))

        # Ensure invoices are created (if not already created at open)
        self._generate_linked_invoices()

        self.state = 'delivered'
        return self.action_view_invoices()
    
    def action_view_invoices(self):
        """Action to view created invoices (from linked SOs or standalone)"""
        # Collect invoices from linked SOs
        invoice_ids = set()
        if self.customer_invoice_id:
            invoice_ids.add(self.customer_invoice_id.id)
        if self.insurance_invoice_id:
            invoice_ids.add(self.insurance_invoice_id.id)
        # Also pull invoices from linked sale orders
        for so in (self.customer_sale_order_id | self.insurance_sale_order_id):
            invoice_ids.update(so.invoice_ids.ids)

        if not invoice_ids:
            raise UserError(_('No invoices have been created for this job card yet.'))

        return {
            'type': 'ir.actions.act_window',
            'name': _('Invoices'),
            'res_model': 'account.move',
            'domain': [('id', 'in', list(invoice_ids))],
            'view_mode': 'list,form',
            'target': 'current',
        }
    
    # NEW: Manual action to create invoices
    def action_manually_create_invoices(self):
        """Manual action to create invoices"""
        if self.invoice_created:
            raise UserError(_('Invoices have already been created for this job card.'))
        
        if not self.analytic_account_id:
            self.analytic_account_id = self._fetch_analytic_account()
        
        self._create_invoices()
        
        return self.action_view_invoices()
    
    @api.model
    def get_dashboard_data(self, user_id=None, date_from=None, date_to=None):
        """Return all dashboard statistics - called from JS"""
        dashboard = self.env['job.card.dashboard']
        return dashboard.get_dashboard_data(
            user_id=user_id, date_from=date_from, date_to=date_to
        )

    @api.model
    def get_overdue_jobs(self, user_id=None, date_from=None, date_to=None):
        """Return overdue job cards - called from JS"""
        dashboard = self.env['job.card.dashboard']
        return dashboard.get_overdue_jobs(
            user_id=user_id, date_from=date_from, date_to=date_to
        )
    

class JobCardLine(models.Model):
    _name = 'job.card.line'
    _description = 'Job Card Line'
    _order = 'sequence, id'

    job_card_id = fields.Many2one('job.card', string='Job Card', ondelete='cascade', index=True)
    parts_job_card_id = fields.Many2one('job.card', string='Job Card (Parts)', ondelete='cascade')
    consumables_job_card_id = fields.Many2one('job.card', string='Job Card (Consumables)', ondelete='cascade')
    repairs_job_card_id = fields.Many2one('job.card', string='Job Card (Repairs)', ondelete='cascade')
    paint_job_card_id = fields.Many2one('job.card', string='Job Card (Paint)', ondelete='cascade')
    sundries_job_card_id = fields.Many2one('job.card', string='Job Card (Sundries)', ondelete='cascade')
    fittings_job_card_id = fields.Many2one('job.card', string='Job Card (Fittings)', ondelete='cascade')
    sequence = fields.Integer(string='Sequence', default=10)
    line_category = fields.Selection(
        [
            ('parts', 'Supply Parts'),
            ('consumables', 'Consumables'),
            ('repairs', 'Repair Works'),
            ('paint', 'Paint Job'),
            ('sundries', 'Sundries'),
            ('fittings', 'Fittings'),
        ],
        string='Category',
        default='parts',
        required=True,
    )
    display_type = fields.Selection([
        ('line_section', 'Section'),
        ('line_note', 'Note'),
    ], string='Line Type', help='Choose section or note line to add headers and descriptions.')
    name = fields.Text(string='Description')
    product_id = fields.Many2one('product.product', string='Product')
    product_uom_id = fields.Many2one('uom.uom', string='Unit of Measure', default=lambda self: self.env.ref('uom.product_uom_unit', raise_if_not_found=False).id if self.env.ref('uom.product_uom_unit', raise_if_not_found=False) else False)
    quantity = fields.Float(string='Quantity', default=1.0)
    unit_price = fields.Float(string='Unit Price')
    tax_ids = fields.Many2many('account.tax', string='Taxes')
    discount = fields.Float(string='Discount (%)', default=0.0)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('line_category'):
                vals['line_category'] = self.env.context.get('default_line_category', 'parts')
        return super().create(vals_list)

    @api.onchange('product_id')
    def _onchange_product_id(self):
        if self.product_id:
            self.name = self.product_id.display_name or self.product_id.name
            self.unit_price = self.product_id.lst_price
            if self.product_id.uom_id:
                self.product_uom_id = self.product_id.uom_id
            self.tax_ids = self.product_id.taxes_id


    def unlink(self):
        for line in self:
            line.write({'tax_ids': [(5, 0, 0)]})
        return super().unlink()

    @api.depends('quantity', 'unit_price', 'discount', 'tax_ids')
    def _compute_amount(self):
        for line in self:
            if line.display_type:
                line.price_subtotal = 0
                line.tax_amount = 0
                line.price_total = 0
            else:
                subtotal = line.quantity * line.unit_price
                if line.discount:
                    subtotal = subtotal * (1 - line.discount / 100.0)
                line.price_subtotal = subtotal
                if line.tax_ids:
                    taxes = line.tax_ids.compute_all(line.unit_price, None, line.quantity, line.product_id)
                    if line.discount:
                        for key in ['total_included', 'total_excluded']:
                            if key in taxes:
                                taxes[key] = taxes[key] * (1 - line.discount / 100.0)
                    line.price_total = taxes.get('total_included', subtotal)
                    line.price_subtotal = taxes.get('total_excluded', subtotal)
                    line.tax_amount = line.price_total - line.price_subtotal
                else:
                    line.price_total = subtotal
                    line.tax_amount = 0

    price_subtotal = fields.Float(string='Subtotal', compute='_compute_amount', store=True)
    tax_amount = fields.Float(string='Tax', compute='_compute_amount', store=True)
    price_total = fields.Float(string='Amount', compute='_compute_amount', store=True)
    rate_2 = fields.Float(string='Rate 2', compute='_compute_rate_2', store=True)

    @api.depends('unit_price')
    def _compute_rate_2(self):
        for line in self:
            line.rate_2 = line.unit_price



class JobCardPortal(CustomerPortal):
    
    def _prepare_home_portal_values(self, counters):
        values = super()._prepare_home_portal_values(counters)
        if 'job_card_count' in counters:
            values['job_card_count'] = request.env['job.card'].search_count([])
        return values
    
    @http_route(['/my/jobcards', '/my/jobcards/page/<int:page>'], type='http', auth="user", website=True)
    def portal_my_jobcards(self, page=1, **kw):
        job_cards = request.env['job.card'].search([])
        return request.render('job_card_management.portal_my_jobcards', {
            'job_cards': job_cards,
            'page_name': 'jobcards',
        })
    
    @http_route(['/my/jobcards/<int:job_card_id>'], type='http', auth="public", website=True)
    def portal_jobcard_detail(self, job_card_id, access_token=None, **kw):
        job_card = request.env['job.card'].sudo().browse(job_card_id)
        if not job_card.exists():
            return request.not_found()
        # If access_token is provided, validate it
        if access_token and job_card.access_token != access_token:
            return request.not_found()
        return request.render('job_card_management.portal_jobcard_detail', {
            'job_card': job_card,
            'page_name': 'jobcard',
        })