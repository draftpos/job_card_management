from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError


class JobConsumableIssue(models.Model):
    _name = 'job.consumable.issue'
    _description = 'Job Consumable Issue'
    _order = 'id desc'
    _rec_name = 'name'

    name = fields.Char(string='Reference', readonly=True, copy=False, default='New')

    job_card_id = fields.Many2one(
        'job.card', string='Job Card', required=True,
        domain="[('state', 'not in', ('draft', 'delivered', 'cancelled')), ('all_consumables_issued', '=', False)]"
    )
    customer_id = fields.Many2one(related='job_card_id.customer_id', string='Customer', store=True)
    vehicle_id = fields.Many2one(related='job_card_id.vehicle_id', string='Vehicle', store=True)

    @api.model
    def _default_source_location(self):
        warehouse = self.env['stock.warehouse'].search([('company_id', '=', self.env.company.id)], limit=1)
        if warehouse:
            return warehouse.lot_stock_id.id
        return False

    @api.model
    def _default_dest_location(self):
        production = self.env['stock.location'].search([
            ('usage', '=', 'production'),
            ('company_id', 'in', [self.env.company.id, False])
        ], limit=1)
        return production.id or False

    source_location_id = fields.Many2one(
        'stock.location', string='Source Location',
        domain=[('usage', '=', 'internal')],
        required=True,
        default=_default_source_location
    )
    dest_location_id = fields.Many2one(
        'stock.location', string='Destination Location',
        domain=[('usage', 'in', ['internal', 'production'])],
        required=True,
        default=_default_dest_location
    )

    state = fields.Selection([
        ('draft', 'Draft'),
        ('confirmed', 'Confirmed'),
        ('issued', 'Issued'),
        ('cancelled', 'Cancelled'),
        ('cancelled', 'Cancelled')
    ], string='Status', default='draft')

    issue_line_ids = fields.One2many('job.consumable.issue.line', 'issue_id', string='Lines')
    stock_picking_id = fields.Many2one('stock.picking', string='Transfer', readonly=True)
    scrap_ids = fields.Many2many('stock.scrap', string='Scraps', readonly=True)
    analytic_distribution = fields.Json(
        string='Analytic Distribution',
        compute='_compute_analytic_distribution', store=True, readonly=False
    )
    notes = fields.Text(string='Notes')
    issue_date = fields.Date(string='Issue Date', default=fields.Date.today)

    @api.depends('job_card_id.analytic_account_id')
    def _compute_analytic_distribution(self):
        for rec in self:
            if rec.job_card_id and rec.job_card_id.analytic_account_id:
                rec.analytic_distribution = {str(rec.job_card_id.analytic_account_id.id): 100.0}
            else:
                rec.analytic_distribution = False

    all_issued = fields.Boolean(string='All Issued', compute='_compute_all_issued', store=True)

    @api.depends('issue_line_ids.issued_qty', 'issue_line_ids.required_qty')
    def _compute_all_issued(self):
        for rec in self:
            rec.all_issued = all(l.issued_qty >= l.required_qty for l in rec.issue_line_ids) if rec.issue_line_ids else False

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                vals['name'] = self.env['ir.sequence'].next_by_code('consumable.issue') or _('New')
        return super().create(vals_list)

    def action_populate_from_job_card(self):
        self.ensure_one()
        if not self.job_card_id:
            raise UserError(_('Please select a Job Card first.'))
        self.issue_line_ids.unlink()
        allow_service = self.env['ir.config_parameter'].sudo().get_param('job_card_management.allow_service_requisition', 'False') == 'True'
        lines_to_create = []
        job_lines = self.job_card_id.consumables_line_ids.filtered(
            lambda l: l.display_type not in ('line_section', 'line_note') and l.product_id
        )
        for line in job_lines:
            product = line.product_id
            is_service = product.type == 'service'
            
            if not allow_service and is_service:
                continue
                
            available_qty = 0.0
            if not is_service and self.source_location_id:
                quants = self.env['stock.quant'].search([
                    ('product_id', '=', product.id),
                    ('location_id', 'child_of', self.source_location_id.id),
                ])
                available_qty = sum(quants.mapped('quantity'))
            lines_to_create.append({
                'issue_id': self.id,
                'product_id': product.id,
                'job_card_line_id': line.id,
                'required_qty': line.quantity,
                'issued_qty': 0.0,
                'available_qty': available_qty,
                'uom_id': line.product_uom_id.id if line.product_uom_id else product.uom_id.id,
                'is_service': is_service,
            })
        if lines_to_create:
            self.env['job.consumable.issue.line'].create(lines_to_create)

    def action_confirm(self):
        self.ensure_one()
        if not self.issue_line_ids:
            raise UserError(_('No lines to issue. Click "Populate from Job Card" first.'))
        self.state = 'confirmed'

    def action_issue(self):
        self.ensure_one()
        if self.state not in ('draft', 'confirmed'):
            raise UserError(_('This issue is already processed or cancelled.'))
        stockable_lines = self.issue_line_ids.filtered(
            lambda l: not l.is_service and l.issued_qty > 0
        )
        if not stockable_lines:
            raise UserError(_('No stockable items with issued quantity > 0.'))

        scrap_location = self.env['stock.location'].search([
            ('scrap_location', '=', True),
            ('company_id', 'in', [self.env.company.id, False])
        ], limit=1)
        if not scrap_location:
            raise UserError(_('No scrap location found.'))

        scraps = self.env['stock.scrap']
        for line in stockable_lines:
            scrap_vals = {
                'product_id': line.product_id.id,
                'scrap_qty': line.issued_qty,
                'product_uom_id': line.uom_id.id or line.product_id.uom_id.id,
                'location_id': self.source_location_id.id,
                'scrap_location_id': scrap_location.id,
                'origin': self.name,
                'analytic_distribution': self.analytic_distribution,
                'company_id': self.env.company.id,
            }
            scrap = self.env['stock.scrap'].create(scrap_vals)
            scrap.action_validate()
            scraps |= scrap

        self.scrap_ids = scraps.ids
        self.state = 'issued'
        self._update_job_card_consumable_state()
        
        scrap_names = ", ".join(scraps.mapped('name'))
        wizard = self.env['consumable.issue.success.wizard'].create({
            'issue_id': self.id,
            'job_card_id': self.job_card_id.id,
            'picking_name': scrap_names,
        })
        
        return {
            'name': 'Consumables Issued',
            'type': 'ir.actions.act_window',
            'res_model': 'consumable.issue.success.wizard',
            'res_id': wizard.id,
            'view_mode': 'form',
            'target': 'new',
        }

    @api.onchange('source_location_id')
    def _onchange_source_location(self):
        if not self.source_location_id:
            for line in self.issue_line_ids:
                line.available_qty = 0.0
            return

        for line in self.issue_line_ids:
            if line.is_service:
                line.available_qty = 0.0
                continue
                
            quants = self.env['stock.quant'].search([
                ('product_id', '=', line.product_id.id),
                ('location_id', 'child_of', self.source_location_id.id),
            ])
            line.available_qty = sum(quants.mapped('quantity'))

    def _update_job_card_consumable_state(self):
        job = self.job_card_id
        if not job:
            return
        all_issues = self.search([('job_card_id', '=', job.id), ('state', '=', 'issued')])
        if all_issues and all(i.all_issued for i in all_issues):
            job.all_consumables_issued = True
        else:
            job.all_consumables_issued = False

    def action_create_requisitions(self):
        self.ensure_one()
        allow_service = self.env['ir.config_parameter'].sudo().get_param('job_card_management.allow_service_requisition', 'False') == 'True'
        
        if allow_service:
            short_lines = self.issue_line_ids.filtered(lambda l: l.shortage_qty > 0)
        else:
            short_lines = self.issue_line_ids.filtered(lambda l: not l.is_service and l.shortage_qty > 0)
            
        if not short_lines:
            raise UserError(_('No items are short in stock.'))
        requisition_lines = [(0, 0, {
            'product_id': l.product_id.id,
            'product_qty': l.shortage_qty,
            'product_uom_id': l.uom_id.id or l.product_id.uom_id.id,
        }) for l in short_lines]
        requisition = self.env['purchase.requisition'].create({
            'line_ids': requisition_lines,
        })
        self.job_card_id.state = 'requisition_started'
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'purchase.requisition',
            'res_id': requisition.id,
            'view_mode': 'form',
        }

    def action_cancel(self):
        self.ensure_one()
        if self.state == 'issued':
            raise UserError(_('Cannot cancel an already issued consumable.issue.'))
        self.state = 'cancelled'

    def action_reset_draft(self):
        self.ensure_one()
        self.state = 'draft'

    def action_view_picking(self):
        self.ensure_one()
        if not self.stock_picking_id:
            raise UserError(_('No transfer linked to this issue.'))
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'stock.picking',
            'res_id': self.stock_picking_id.id,
            'view_mode': 'form',
        }


class JobConsumableIssueLine(models.Model):
    _name = 'job.consumable.issue.line'
    _description = 'Job Consumable Issue Line'

    issue_id = fields.Many2one('job.consumable.issue', string='Issue', ondelete='cascade')
    job_card_line_id = fields.Many2one('job.card.line', string='Job Card Line')
    product_id = fields.Many2one('product.product', string='Product', required=True)
    uom_id = fields.Many2one('uom.uom', string='Unit of Measure')
    required_qty = fields.Float(string='Required Qty', default=1.0)
    available_qty = fields.Float(string='Available in Stock', readonly=True)
    issued_qty = fields.Float(string='Issued Qty', default=0.0)
    balance_qty = fields.Float(string='Balance', compute='_compute_balance', store=True)
    shortage_qty = fields.Float(string='Shortage', compute='_compute_shortage', store=True)
    cost_price = fields.Float(string='Cost Price', related='product_id.standard_price', readonly=True)
    is_service = fields.Boolean(string='Service Item', default=False)

    @api.depends('required_qty', 'issued_qty')
    def _compute_balance(self):
        for rec in self:
            rec.balance_qty = max(rec.required_qty - rec.issued_qty, 0)

    @api.depends('required_qty', 'available_qty')
    def _compute_shortage(self):
        for rec in self:
            rec.shortage_qty = max(rec.required_qty - rec.available_qty, 0)

    @api.constrains('issued_qty', 'required_qty')
    def _check_issued_qty(self):
        for rec in self:
            if rec.issued_qty < 0:
                raise ValidationError(_('Issued quantity cannot be negative.'))
            if rec.issued_qty > rec.required_qty:
                raise ValidationError(
                    _('Issued qty (%s) cannot exceed required qty (%s) for %s.') % (
                        rec.issued_qty, rec.required_qty, rec.product_id.name
                    )
                )
