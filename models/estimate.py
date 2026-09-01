import uuid
from datetime import timedelta

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError
from odoo.http import request, route as http_route
from odoo.addons.portal.controllers.portal import CustomerPortal  # type: ignore


LINE_CATEGORY_SELECTION = [
    ('parts', 'Supply Parts'),
    ('consumables', 'Consumables'),
    ('repairs', 'Repair Works'),
    ('paint', 'Paint Job'),
    ('sundries', 'Sundries'),
    ('fittings', 'Fittings'),
]


class Estimate(models.Model):
    _name = 'estimate'
    _description = 'Quotation / Quote'
    _inherit = ['job.card.backend.navigation.mixin', 'mail.thread', 'mail.activity.mixin']
    _order = 'id desc'

    def _default_name(self):
        """Generate next EST-XXXX number, considering both EST- and LOC-EST- prefixes."""
        self.env.cr.execute("""
            SELECT name FROM estimate
            WHERE name ~ '^(LOC-)?EST-[0-9]+$'
        """)
        rows = self.env.cr.fetchall()
        max_num = 1000
        for (name,) in rows:
            # strip optional LOC- prefix, then EST- prefix, parse the number
            stripped = name
            if stripped.startswith('LOC-'):
                stripped = stripped[4:]   # remove LOC-
            if stripped.startswith('EST-'):
                try:
                    num = int(stripped[4:])
                    if num > max_num:
                        max_num = num
                except ValueError:
                    pass
        return f'EST-{max_num + 1}'

    name = fields.Char(
        string='Estimate NO:',
        required=True,
        default=_default_name,
        readonly=True,
        copy=False,
    )
    customer_id = fields.Many2one('customer', string='Customer', required=True)
    insurance_company_id = fields.Many2one(
        'customer',
        string='Insurance Company',
        domain="[('customer_type', '=', 'insurance')]",
        help='Select or create an insurance company'
    )
    excess_percentage = fields.Float(
        string='Excess (%)',
        default=0.0,
        help='Percentage of the total paid by the customer (excess). Insurance pays the rest.'
    )
    insurance_percentage = fields.Float(
        string='Insurance Pays (%)',
        compute='_compute_insurance_pct',
        store=True,
        help='Automatically computed as 100 minus the excess percentage.'
    )
    excess_amount = fields.Float(string='Excess AMT', default=0.0)
    insurance_amount = fields.Float(string='Insurance AMT', default=0.0)

    authorization_type = fields.Selection([
        ('file', 'File'),
        ('link', 'Link')
    ], string='Authorization Type', default='file')
    authorization_letter = fields.Binary(string='Authorization Letter')
    authorization_letter_filename = fields.Char(string='Authorization Letter Filename')
    authorization_link = fields.Char(string='Authorization Link')

    betterment_percentage = fields.Float(string='Betterment (%)', default=0.0)
    betterment_amount = fields.Float(string='Betterment AMT', default=0.0)

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


    insurance_sale_order_id = fields.Many2one('sale.order', string='Insurance Sale Order')
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
    vehicle_name = fields.Char(
        related='vehicle_id.name',
        string='Vehicle Name',
        readonly=True,
    )
    vehicle_model = fields.Char(related='vehicle_id.model_id.name', string='Vehicle Model', readonly=True)
    vehicle_make = fields.Char(related='vehicle_id.make_id.name', string='Vehicle Make', readonly=True)
    vehicle_chassis_number = fields.Char(related='vehicle_id.chassis_number', string='Vehicle Chassis', readonly=True)
    vehicle_year_of_manufacture = fields.Integer(related='vehicle_id.year_of_manufacture', string='Year of Manufacture', readonly=True)
    vehicle_display = fields.Char(
        string='Vehicle',
        compute='_compute_vehicle_display',
        readonly=True,
    )
    analytic_account_id = fields.Many2one('account.analytic.account', string='Analytic Account')
    state = fields.Selection([
        ('draft', 'Draft'),
        ('submitted', 'Submitted'),
        ('approved', 'Approved'),
        ('converted', 'Converted'),
    ], default='draft')
    has_job_card = fields.Boolean(string='Job Card Opened', default=False)
    job_card_id = fields.Many2one('job.card', string='Linked Job Card')
    sale_order_id = fields.Many2one('sale.order', string='Sales Order')
    terms_and_conditions = fields.Html(
        string='Terms and Conditions',
        default=lambda self: self.env['ir.config_parameter'].sudo().get_param('job_card_management.default_terms', '')
    )
    estimate_lines = fields.One2many('estimate.line', 'estimate_id', string='Lines', copy=True)
    parts_line_ids = fields.One2many(
        'estimate.line', 'parts_estimate_id', string='Supply Parts',
        domain=[('line_category', '=', 'parts')],
    )
    consumables_line_ids = fields.One2many(
        'estimate.line', 'consumables_estimate_id', string='Consumables',
        domain=[('line_category', '=', 'consumables')],
    )
    repairs_line_ids = fields.One2many(
        'estimate.line', 'repairs_estimate_id', string='Repair Works',
        domain=[('line_category', '=', 'repairs')],
    )
    paint_line_ids = fields.One2many(
        'estimate.line', 'paint_estimate_id', string='Paint Job',
        domain=[('line_category', '=', 'paint')],
    )
    sundries_line_ids = fields.One2many(
        'estimate.line', 'sundries_estimate_id', string='Sundries',
        domain=[('line_category', '=', 'sundries')],
    )
    fittings_line_ids = fields.One2many(
        'estimate.line', 'fittings_estimate_id', string='Fittings',
        domain=[('line_category', '=', 'fittings')],
    )
    access_token = fields.Char('Access Token', copy=False)

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        if 'customer_id' in fields_list and not res.get('customer_id'):
            if self.env.context.get('default_customer_id'):
                res['customer_id'] = self.env.context['default_customer_id']
            elif (
                self.env.context.get('active_model') == 'customer'
                and self.env.context.get('active_id')
            ):
                res['customer_id'] = self.env.context['active_id']
        
        # Auto-populate Consumables and Sundries
        cons_prod = self.env['product.product'].search([('name', '=', 'Consumables')], limit=1)
        if not cons_prod:
            cons_prod = self.env['product.product'].create({'name': 'Consumables', 'type': 'service'})
        
        sundries_prod = self.env['product.product'].search([('name', '=', 'Sundries')], limit=1)
        if not sundries_prod:
            sundries_prod = self.env['product.product'].create({'name': 'Sundries', 'type': 'service'})

        cons_lines = res.get('consumables_line_ids', [])
        cons_lines.append((0, 0, {
            'line_category': 'consumables',
            'product_id': cons_prod.id,
            'name': cons_prod.name,
            'quantity': 1.0,
        }))
        res['consumables_line_ids'] = cons_lines

        sundries_lines = res.get('sundries_line_ids', [])
        sundries_lines.append((0, 0, {
            'line_category': 'sundries',
            'product_id': sundries_prod.id,
            'name': sundries_prod.name,
            'quantity': 1.0,
        }))
        res['sundries_line_ids'] = sundries_lines
        
        return res

    @api.model
    def create(self, vals):
        if isinstance(vals, list):
            for v in vals:
                if not v.get('name') or v.get('name') == 'New':
                    v['name'] = self._default_name()
        else:
            if not vals.get('name') or vals.get('name') == 'New':
                vals['name'] = self._default_name()
        records = super().create(vals)

        for record in records:
            # Auto-populate Consumables product line
            consumables_product = self.env['product.product'].search(
                [('name', 'ilike', 'Consumables')], limit=1
            )
            if not consumables_product:
                consumables_product = self.env['product.product'].create({
                    'name': 'Consumables',
                    'type': 'service',
                    'default_code': 'CONS',
                })
            
            if consumables_product:
                self.env['estimate.line'].create({
                    'estimate_id': record.id,
                    'consumables_estimate_id': record.id,
                    'line_category': 'consumables',
                    'product_id': consumables_product.id,
                    'name': consumables_product.name,
                    'quantity': 1.0,
                    'unit_price': 0.0,
                })

            # Auto-populate Sundries product line
            sundries_product = self.env['product.product'].search(
                [('name', 'ilike', 'Sundries')], limit=1
            )
            if not sundries_product:
                sundries_product = self.env['product.product'].create({
                    'name': 'Sundries',
                    'type': 'service',
                    'default_code': 'SUND',
                })
                
            if sundries_product:
                self.env['estimate.line'].create({
                    'estimate_id': record.id,
                    'sundries_estimate_id': record.id,
                    'line_category': 'sundries',
                    'product_id': sundries_product.id,
                    'name': sundries_product.name,
                    'quantity': 1.0,
                    'unit_price': 0.0,
                })

        records._organize_lines()
        return records


    def write(self, vals):
        locked_fields = {'customer_id', 'name', 'vehicle_id'}
        if locked_fields.intersection(vals.keys()):
            for estimate in self:
                if estimate.state in ('approved', 'converted'):
                    raise UserError(_(
                        'Cannot change customer, estimate number, or vehicle on an approved '
                        'estimate. Use Redo first.'
                    ))
        res = super().write(vals)
        self._organize_lines()
        return res

    def _organize_lines(self):
        categories = ['parts', 'consumables', 'repairs', 'paint', 'sundries', 'fittings']
        category_names = dict(LINE_CATEGORY_SELECTION)
        base_seq = {'parts': 1000, 'consumables': 1500, 'repairs': 2000, 'paint': 3000, 'sundries': 3500, 'fittings': 4000}

        for record in self:
            lines = record.estimate_lines
            for cat in categories:
                cat_lines = lines.filtered(lambda l: l.line_category == cat and not l.display_type)
                cat_notes = lines.filtered(lambda l: l.line_category == cat and l.display_type == 'line_note')
                
                if cat_lines or cat_notes:
                    section = lines.filtered(lambda l: l.line_category == cat and l.display_type == 'line_section')
                    if not section:
                        section = self.env['estimate.line'].create({
                            'estimate_id': record.id,
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

    @api.depends(
        'estimate_lines.price_subtotal', 'estimate_lines.price_total',
        'parts_line_ids.price_subtotal', 'parts_line_ids.price_total',
        'consumables_line_ids.price_subtotal', 'consumables_line_ids.price_total',
        'repairs_line_ids.price_subtotal', 'repairs_line_ids.price_total',
        'paint_line_ids.price_subtotal', 'paint_line_ids.price_total',
        'sundries_line_ids.price_subtotal', 'sundries_line_ids.price_total',
        'fittings_line_ids.price_subtotal', 'fittings_line_ids.price_total'
    )
    def _compute_totals(self):
        for estimate in self:
            all_lines = estimate.estimate_lines | estimate.parts_line_ids | estimate.consumables_line_ids | estimate.repairs_line_ids | estimate.paint_line_ids | estimate.sundries_line_ids | estimate.fittings_line_ids
            lines = all_lines.filtered(lambda l: not l.display_type)
            estimate.amount_untaxed = sum(lines.mapped('price_subtotal'))
            estimate.amount_tax = sum(lines.mapped(lambda l: l.price_total - l.price_subtotal))
            estimate.amount_total = estimate.amount_untaxed + estimate.amount_tax

    def _organize_sections(self):
        categories = ['parts', 'consumables', 'repairs', 'paint', 'sundries', 'fittings']
        category_names = dict(LINE_CATEGORY_SELECTION)
        base_seq = {'parts': 1000, 'consumables': 1500, 'repairs': 2000, 'paint': 3000, 'sundries': 3500, 'fittings': 4000}
        
        for rec in self:
            for cat in categories:
                # Get lines from the specific category tab
                cat_lines = getattr(rec, f'{cat}_line_ids').filtered(lambda l: l.display_type != 'line_section')
                if cat_lines:
                    # Link them to the main order lines
                    for line in cat_lines:
                        line.estimate_id = rec.id

                    section = rec.estimate_lines.filtered(lambda l: l.line_category == cat and l.display_type == 'line_section')
                    if not section:
                        self.env['estimate.line'].create({
                            'estimate_id': rec.id,
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
        records = super().create(vals_list)
        records._organize_sections()
        return records

    def write(self, vals):
        res = super().write(vals)
        self._organize_sections()
        return res

    amount_untaxed = fields.Float(string='Total Excl', compute='_compute_totals')
    amount_tax = fields.Float(string='Total Tax', compute='_compute_totals')
    amount_total = fields.Float(string='Total Incl', compute='_compute_totals')

    def _job_card_form_action_xmlid(self):
        return 'job_card_management.action_estimate'

    @api.depends('vehicle_id', 'vehicle_id.registration_number', 'vehicle_id.make_id.name', 'vehicle_id.model_id.name')
    def _compute_vehicle_display(self):
        Vehicle = self.env['vehicle']
        for estimate in self:
            if estimate.vehicle_id:
                estimate.vehicle_display = Vehicle._format_display_name(estimate.vehicle_id)
            else:
                estimate.vehicle_display = False

    @api.onchange('customer_id')
    def _onchange_customer_id(self):
        if self.vehicle_id and self.vehicle_id.customer_id not in (False, self.customer_id):
            self.vehicle_id = False

    def _generate_access_token(self):
        if not self.access_token:
            self.access_token = str(uuid.uuid4())

    def get_portal_url(self, suffix=None, report_type=None):
        self.ensure_one()
        if not self.access_token:
            self._generate_access_token()
        url = f'/my/estimates/{self.id}?access_token={self.access_token}'
        if suffix:
            url += f'/{suffix}'
        if report_type:
            url += f'&report_type={report_type}'
        return url

    def action_submit(self):
        self.state = 'submitted'

    @api.depends('excess_amount', 'betterment_amount', 'amount_total', 'insurance_company_id')
    def _compute_insurance_pct(self):
        for rec in self:
            amount = rec.amount_total or 0.0
            if not rec.insurance_company_id:
                rec.insurance_amount = 0.0
                rec.insurance_percentage = 0.0
            else:
                rec.insurance_amount = amount - (rec.excess_amount + rec.betterment_amount)
                if amount > 0:
                    rec.insurance_percentage = (rec.insurance_amount / amount) * 100.0
                else:
                    rec.insurance_percentage = 0.0

    @api.onchange('insurance_company_id')
    def _onchange_insurance_company_defaults(self):
        if not self.insurance_company_id:
            self.excess_amount = 0.0
            self.betterment_amount = 0.0

    @api.onchange('betterment_percentage', 'amount_total')
    def _onchange_betterment_percentage(self):
        if self.betterment_billing_policy_setting == 'percentage':
            if self.amount_total:
                self.betterment_amount = (self.betterment_percentage / 100) * self.amount_total
            else:
                self.betterment_amount = 0.0

    @api.onchange('excess_amount', 'betterment_amount', 'amount_total')
    def _onchange_insurance_totals(self):
        amount = self.amount_total or 0.0
        self.insurance_amount = amount - (self.excess_amount + self.betterment_amount)
        if amount > 0:
            self.insurance_percentage = (self.insurance_amount / amount) * 100
        else:
            self.insurance_percentage = 0.0

    @api.constrains('authorization_letter_filename')
    def _check_authorization_file_extension(self):
        for rec in self:
            if rec.authorization_letter_filename:
                allowed_extensions = ('.pdf', '.txt', '.doc', '.docx')
                if not rec.authorization_letter_filename.lower().endswith(allowed_extensions):
                    raise ValidationError("The authorization letter must be a PDF, TXT, DOC, or DOCX file.")

    @api.constrains('excess_amount', 'betterment_amount', 'amount_total')
    def _check_insurance_amounts(self):
        for rec in self:
            if rec.excess_amount < 0 or rec.betterment_amount < 0:
                raise ValidationError("Excess and Betterment amounts must be positive.")
            if round(rec.excess_amount + rec.betterment_amount, 2) > round(rec.amount_total, 2):
                raise ValidationError("The sum of Excess and Betterment amounts cannot exceed the Total Invoice amount.")

    def _build_so_lines(self, price_multiplier=1.0):
        """Build sale order lines from estimate lines, applying a price multiplier for splits."""
        lines = []
        for line in self.estimate_lines:
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

    def action_approve(self):
        if not self.env.user.has_group('job_card_management.group_can_approve_estimate'):
            raise UserError(_('You are not allowed to approve estimates.'))
        self.state = 'approved'
        self._generate_access_token()

        if not self.customer_id.partner_id:
            raise UserError(_('Customer has no linked partner. Please save the customer again.'))

    def action_redo(self):
        if not self.env.user.has_group('job_card_management.group_can_redo_estimate'):
            raise UserError(_('You do not have permission to redo estimates. Please contact your administrator.'))

        for estimate in self:
            if estimate.state not in ('approved', 'converted'):
                raise UserError(_('Only approved or converted estimates can be redone.'))
            if estimate.sale_order_id:
                sale_order = estimate.sale_order_id
                if sale_order.state not in ('cancel', 'done'):
                    sale_order.action_cancel()
                estimate.sale_order_id = False
            if estimate.insurance_sale_order_id:
                insurance_so = estimate.insurance_sale_order_id
                if insurance_so.state not in ('cancel', 'done'):
                    insurance_so.action_cancel()
                estimate.insurance_sale_order_id = False
            estimate.state = 'draft'

    def action_open_job_card(self):
        if not self.env.user.has_group('job_card_management.group_can_open_job_card'):
            raise UserError(_('You are not allowed to open a job.'))
        if self.has_job_card:
            raise UserError(_('Job card already opened for this estimate.'))

        today = fields.Date.today()
        job_card = self.env['job.card'].with_context(skip_default_lines=True).create({
            'estimate_id': self.id,
            'customer_id': self.customer_id.id,
            'second_customer_id': self.insurance_company_id.id if self.insurance_company_id else False,
            'vehicle_id': self.vehicle_id.id,
            'start_date': today,
        })
        for line in self.estimate_lines:
            line_vals = {
                'job_card_id': job_card.id,
                'sequence': line.sequence,
                'display_type': line.display_type,
                'name': line.name if line.name else (line.product_id.name if line.product_id else ''),
                'line_category': line.line_category,
                'product_id': line.product_id.id if line.product_id else False,
                'product_uom_id': line.product_uom_id.id if line.product_uom_id else False,
                'quantity': line.quantity,
                'unit_price': line.unit_price,
                'discount': line.discount,
            }
            if line.line_category:
                line_vals[f'{line.line_category}_job_card_id'] = job_card.id
            if line.tax_ids:
                line_vals['tax_ids'] = [(6, 0, line.tax_ids.ids)]
            self.env['job.card.line'].create(line_vals)
            
        job_card.write({
            'excess_percentage': self.excess_percentage,
            'excess_amount': self.excess_amount,
            'betterment_percentage': self.betterment_percentage,
            'betterment_amount': self.betterment_amount,
        })
            
        self.write({
            'has_job_card': True,
            'job_card_id': job_card.id,
            'state': 'converted',
        })
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'job.card',
            'res_id': job_card.id,
            'view_mode': 'form',
        }

    def action_preview_estimate(self):
        report = self.env.ref('job_card_management.action_report_estimate')
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

    def action_send_whatsapp(self):
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'WhatsApp Integration',
                'message': 'WhatsApp module is not installed. Please install the WhatsApp integration module.',
                'type': 'warning',
                'sticky': False,
            },
        }

    def action_send_email(self):
        self.ensure_one()
        report = self.env.ref('job_card_management.action_report_estimate', raise_if_not_found=False)
        if not report:
            raise UserError('Estimate report not found.')

        pdf_content, _ = self.env['ir.actions.report']._render_qweb_pdf(report.report_name, [self.id])

        attachment = self.env['ir.attachment'].create({
            'name': f'{self.name}.pdf',
            'raw': pdf_content,
            'res_model': 'estimate',
            'res_id': self.id,
            'mimetype': 'application/pdf',
        })

        customer_email = self.customer_id.email
        if not customer_email:
            raise UserError('Customer does not have an email address.')

        reg = self.vehicle_reg_number or ''
        body = f"""
        <p>Dear {self.customer_id.name},</p>
        <p>Please find attached estimate <strong>{self.name}</strong> for your vehicle
        <strong>{reg}</strong> ({self.vehicle_model}).</p>
        <p>Total: <strong>${self.amount_total:,.2f}</strong></p>
        <p>Best regards,</p>
        """

        compose_ctx = {
            'default_model': 'estimate',
            'default_res_ids': [self.id],
            'default_use_template': False,
            'default_composition_mode': 'comment',
            'default_email_layout_xmlid': 'mail.mail_notification_layout',
            'default_attachment_ids': [(4, attachment.id)],
            'default_subject': f'Estimate {self.name} for {reg}',
            'default_body': body,
            'default_email_to': customer_email,
            'default_partner_ids': [],
        }
        if self.customer_id.partner_id:
            compose_ctx['default_partner_ids'] = [(4, self.customer_id.partner_id.id)]

        return {
            'type': 'ir.actions.act_window',
            'name': 'Send Estimate by Email',
            'res_model': 'mail.compose.message',
            'view_mode': 'form',
            'view_id': self.env.ref('mail.email_compose_message_wizard_form').id,
            'target': 'new',
            'context': compose_ctx,
        }


class EstimateLine(models.Model):
    _name = 'estimate.line'
    _description = 'Quotation Line'
    _order = 'sequence, id'

    estimate_id = fields.Many2one('estimate', string='Estimate', ondelete='cascade')
    parts_estimate_id = fields.Many2one('estimate', string='Estimate (Parts)', ondelete='cascade')
    consumables_estimate_id = fields.Many2one('estimate', string='Estimate (Consumables)', ondelete='cascade')
    repairs_estimate_id = fields.Many2one('estimate', string='Estimate (Repairs)', ondelete='cascade')
    paint_estimate_id = fields.Many2one('estimate', string='Estimate (Paint)', ondelete='cascade')
    sundries_estimate_id = fields.Many2one('estimate', string='Estimate (Sundries)', ondelete='cascade')
    fittings_estimate_id = fields.Many2one('estimate', string='Estimate (Fittings)', ondelete='cascade')
    sequence = fields.Integer(string='Sequence', default=10)
    line_category = fields.Selection(
        LINE_CATEGORY_SELECTION,
        string='Category',
        default='parts',
        required=True,
    )
    display_type = fields.Selection([
        ('line_section', 'Section'),
        ('line_note', 'Note'),
    ], string='Line Type')
    name = fields.Text(string='Description')
    product_id = fields.Many2one('product.product', string='Product')
    product_uom_id = fields.Many2one(
        'uom.uom',
        string='Unit of Measure',
        default=lambda self: self.env.ref('uom.product_uom_unit', raise_if_not_found=False).id,
    )
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
                    taxes_data = line.tax_ids.compute_all(
                        line.unit_price, None, line.quantity, line.product_id,
                    )
                    if line.discount:
                        for key in ('total_included', 'total_excluded'):
                            if key in taxes_data:
                                taxes_data[key] = taxes_data[key] * (1 - line.discount / 100.0)
                    line.price_total = taxes_data.get('total_included', subtotal)
                    line.price_subtotal = taxes_data.get('total_excluded', subtotal)
                    line.tax_amount = line.price_total - line.price_subtotal
                else:
                    line.price_total = subtotal
                    line.tax_amount = 0

    price_subtotal = fields.Float(string='Subtotal', compute='_compute_amount', store=True)
    tax_amount = fields.Float(string='Tax', compute='_compute_amount', store=True)
    price_total = fields.Float(string='Amount', compute='_compute_amount', store=True)


class EstimatePortal(CustomerPortal):

    def _prepare_home_portal_values(self, counters):
        values = super()._prepare_home_portal_values(counters)
        if 'estimate_count' in counters:
            values['estimate_count'] = request.env['estimate'].search_count([])
        return values

    @http_route(['/my/estimates', '/my/estimates/page/<int:page>'], type='http', auth="user", website=True)
    def portal_my_estimates(self, page=1, **kw):
        estimates = request.env['estimate'].search([])
        return request.render('job_card_management.portal_my_estimates', {
            'estimates': estimates,
            'page_name': 'estimates',
        })

    @http_route(['/my/estimates/<int:estimate_id>'], type='http', auth="public", website=True)
    def portal_estimate_detail(self, estimate_id, access_token=None, **kw):
        estimate = request.env['estimate'].sudo().browse(estimate_id)
        if not estimate.exists():
            return request.not_found()
        if access_token and estimate.access_token != access_token:
            return request.not_found()
        return request.render('job_card_management.portal_estimate_detail', {
            'estimate': estimate,
            'page_name': 'estimate',
        })
