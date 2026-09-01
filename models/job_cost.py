from odoo import models, fields, api

class JobCost(models.Model):
    _name = 'job.cost'
    _description = 'Job Cost Breakdown'

    name = fields.Char(string='Reference', compute='_compute_name', store=True)
    job_card_id = fields.Many2one('job.card', string='Job Card', required=True, ondelete='cascade')
    
    cost_line_ids = fields.One2many('job.cost.line', 'job_cost_id', string='Cost Lines')
    total_cost = fields.Float(string='Total Cost', compute='_compute_total_cost', store=True)

    @api.depends('job_card_id')
    def _compute_name(self):
        for rec in self:
            rec.name = f"Costing for {rec.job_card_id.name}" if rec.job_card_id else "New Costing"

    @api.depends('cost_line_ids.total')
    def _compute_total_cost(self):
        for rec in self:
            rec.total_cost = sum(rec.cost_line_ids.mapped('total'))

    @api.model
    def _get_latest_cost(self, product):
        if not product:
            return 0.0
        # 1. Try to get the latest procurement line for this product
        proc_line = self.env['procurement.line'].search([
            ('product_id', '=', product.id),
            ('type', '=', 'purchase_order'),
            ('procurement_id.state', 'in', ['approved', 'purchase_order_created'])
        ], order='create_date desc', limit=1)
        if proc_line and proc_line.buying_price:
            return proc_line.buying_price
        
        # 2. Try to get from actual purchase orders
        pol = self.env['purchase.order.line'].search([
            ('product_id', '=', product.id),
            ('state', 'in', ['purchase', 'done'])
        ], order='create_date desc', limit=1)
        if pol and pol.price_unit:
            return pol.price_unit
            
        # 3. Fallback to standard price
        return product.standard_price

    def compute_costs(self):
        self.ensure_one()
        self.cost_line_ids.unlink()
        
        lines = []
        
        # Mapping job card line categories to cost line categories
        # The user wants to see all items on the job card (the planned items), 
        # NOT the actual inventory issues or procurements, but with their most recent buying price.
        
        category_map = {
            'parts': 'parts',
            'repairs': 'repairs',
            'paint': 'paint',
            'fittings': 'fittings',
            'labour': 'labour',
            'sundries': 'sundries',
            'consumables': 'consumables',
        }
        
        for line in self.job_card_id.job_card_lines.filtered(lambda l: not l.display_type):
            cost_price = self._get_latest_cost(line.product_id)
            cat = category_map.get(line.line_category, 'parts')
            
            lines.append((0, 0, {
                'category': cat,
                'product_id': line.product_id.id if line.product_id else False,
                'description': line.name or (line.product_id.name if line.product_id else ''),
                'quantity': line.quantity,
                'unit_cost': cost_price,
                'total': line.quantity * cost_price,
            }))
            
        # Add actually issued consumables
        issued_consumables = self.job_card_id.consumable_issue_ids.filtered(lambda i: i.state == 'issued')
        for issue in issued_consumables:
            for issue_line in issue.issue_line_ids.filtered(lambda l: l.issued_qty > 0):
                cost_price = issue_line.product_id.standard_price
                lines.append((0, 0, {
                    'category': 'consumables',
                    'product_id': issue_line.product_id.id,
                    'description': f"{issue.name}: {issue_line.product_id.name}",
                    'quantity': issue_line.issued_qty,
                    'unit_cost': cost_price,
                    'total': issue_line.issued_qty * cost_price,
                }))
            
        self.cost_line_ids = lines


class JobCostLine(models.Model):
    _name = 'job.cost.line'
    _description = 'Job Cost Line'

    job_cost_id = fields.Many2one('job.cost', string='Job Cost', ondelete='cascade')
    category = fields.Selection([
        ('parts', 'Parts'),
        ('repairs', 'Repairs'),
        ('paint', 'Paint'),
        ('fittings', 'Fittings'),
        ('labour', 'Labour'),
        ('sundries', 'Sundries'),
        ('consumables', 'Consumables'),
    ], string='Category')
    product_id = fields.Many2one('product.product', string='Product')
    description = fields.Char(string='Description')
    quantity = fields.Float(string='Quantity')
    unit_cost = fields.Float(string='Unit Cost')
    total = fields.Float(string='Total')
