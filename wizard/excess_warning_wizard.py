from odoo import models, fields, api, _
from odoo.exceptions import UserError


class JobCardExcessWarningWizard(models.TransientModel):
    _name = 'job.card.excess.warning.wizard'
    _description = 'Excess Amount Zero Warning'

    job_card_id = fields.Many2one('job.card', string='Job Card', required=True)
    reason = fields.Char(
        string='Reason for Zero Excess',
        required=True,
        help='Provide a reason why the Excess Amount is left as zero.'
    )

    def action_proceed(self):
        """Save reason and proceed with approval"""
        self.ensure_one()
        if not self.reason:
            raise UserError(_('Please provide a reason for the zero excess amount.'))
        job = self.job_card_id
        job.excess_warning_reason = self.reason
        # Log reason to chatter
        job.message_post(
            body=_('⚠️ Job Card approved with zero Excess Amount. Reason: %s') % self.reason,
            message_type='comment',
            subtype_xmlid='mail.mt_note',
        )
        # Now trigger the real approval (excess_warning_reason is set, so no infinite loop)
        job.action_approve_job_card()
        return {'type': 'ir.actions.act_window_close'}
