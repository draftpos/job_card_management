/** @odoo-module **/

import { registry } from "@web/core/registry";
import { Component, useState, onMounted, onWillUnmount, xml } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";

class ConsumableRedirectCountdown extends Component {
    static template = xml`
        <div class="text-center py-4 px-3">
            <!-- Big success icon -->
            <div style="font-size: 4rem; color: #28a745; margin-bottom: 1rem;">
                <i class="fa fa-check-circle"/>
            </div>

            <!-- Title -->
            <h3 style="color: #28a745; font-weight: 700; margin-bottom: 0.5rem;">
                Consumables Issued Successfully!
            </h3>

            <!-- Transfer name -->
            <p class="text-muted" style="font-size: 0.95rem; margin-bottom: 1.5rem;">
                Transfer <strong t-esc="pickingName"/> has been created and confirmed.
            </p>

            <!-- Countdown circle -->
            <div style="
                display: inline-flex;
                align-items: center;
                justify-content: center;
                width: 70px;
                height: 70px;
                border-radius: 50%;
                background: #007bff;
                color: white;
                font-size: 2rem;
                font-weight: bold;
                margin-bottom: 1rem;
                box-shadow: 0 4px 15px rgba(0,123,255,0.4);
            ">
                <span t-esc="state.count"/>
            </div>

            <!-- Redirect message -->
            <p class="text-muted" style="font-size: 0.9rem;">
                Redirecting to <strong>Job Card</strong> in <strong t-esc="state.count"/> second<t t-if="state.count !== 1">s</t>...
            </p>
        </div>
    `;

    static props = {
        record: Object,
        readonly: { type: Boolean, optional: true },
        id: { type: String, optional: true },
    };

    setup() {
        this.state = useState({ count: 5 });
        this.actionService = useService("action");
        this._timer = null;

        onMounted(() => {
            this._timer = setInterval(() => {
                this.state.count -= 1;
                if (this.state.count <= 0) {
                    clearInterval(this._timer);
                    this._timer = null;
                    const jobCardId = this.props.record.data.job_card_id
                        ? this.props.record.data.job_card_id[0]
                        : null;
                    if (jobCardId) {
                        this.actionService.doAction({
                            type: "ir.actions.act_window",
                            res_model: "job.card",
                            res_id: jobCardId,
                            view_mode: "form",
                            target: "current",
                        });
                    }
                }
            }, 1000);
        });

        onWillUnmount(() => {
            if (this._timer) {
                clearInterval(this._timer);
                this._timer = null;
            }
        });
    }

    get pickingName() {
        return this.props.record.data.picking_name || "";
    }
}

registry.category("view_widgets").add("consumable_redirect_countdown", {
    component: ConsumableRedirectCountdown,
});
