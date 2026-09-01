from odoo import models, fields


class ConsumableIssueSuccessWizard(models.TransientModel):
    _name = 'consumable.issue.success.wizard'
    _description = 'Consumable Issue Success Redirect'

    issue_id = fields.Many2one('job.consumable.issue', string='Issue')
    job_card_id = fields.Many2one('job.card', string='Job Card', required=True)
    picking_name = fields.Char(string='Transfer Reference')
    # Dummy field used as anchor for the countdown OWL widget
    countdown_placeholder = fields.Char(string='Countdown', default='5')

    def action_go_to_job_card(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'job.card',
            'res_id': self.job_card_id.id,
            'view_mode': 'form',
            'target': 'current',
        }
