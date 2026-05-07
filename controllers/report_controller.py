import json
from odoo import http
from odoo.http import request


class JobCardReportController(http.Controller):

    @http.route('/job_card_management/report/preview', type='http', auth='user', methods=['POST'], csrf=False)
    def report_preview(self, **kwargs):
        """Generate PDF for preview"""
        data = json.loads(request.httprequest.data)
        record_id = int(data.get('record_id', 0))
        report_xml_id = data.get('report_name', '')

        if not record_id or not report_xml_id:
            return request.not_found()

        report_action = None
        
        # Try 1: Search by report_name field directly
        report_action = request.env['ir.actions.report'].search([
            ('report_name', '=', report_xml_id)
        ], limit=1)
        
        # Try 2: Search by XML ID (ref)
        if not report_action:
            try:
                obj = request.env.ref(report_xml_id)
                if obj._name == 'ir.actions.report':
                    report_action = obj
            except:
                pass
        
        # Try 3: If XML ID points to a template, find the action that uses it
        if not report_action:
            report_action = request.env['ir.actions.report'].search([
                '|',
                ('report_name', '=', report_xml_id),
                ('report_file', '=', report_xml_id),
            ], limit=1)

        if not report_action:
            return request.make_response(
                json.dumps({'error': f'Report not found: {report_xml_id}'}),
                [('Content-Type', 'application/json')]
            )

        pdf_content, _ = request.env['ir.actions.report']._render_qweb_pdf(
            report_action.report_name, [record_id]
        )

        return request.make_response(pdf_content, [
            ('Content-Type', 'application/pdf'),
            ('Content-Length', str(len(pdf_content))),
        ])

    @http.route('/job_card_management/report/view/<string:model>/<int:record_id>/<string:report_name>/<string:title>', type='http', auth='user')
    def report_view(self, model, record_id, report_name, title, **kwargs):
        return request.render('job_card_management.report_preview_page', {
            'record_id': record_id,
            'report_name': report_name,
            'title': title.replace('%20', ' '),
        })