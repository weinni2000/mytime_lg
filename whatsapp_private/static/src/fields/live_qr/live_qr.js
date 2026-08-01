/** @odoo-module **/

import {registry} from "@web/core/registry";
import {useService} from "@web/core/utils/hooks";
import {standardFieldProps} from "@web/views/fields/standard_field_props";
import {Component, onMounted, onWillStart, onWillUnmount, useState} from "@odoo/owl";

export class WhatsAppPrivateLiveQr extends Component {
    static template = "whatsapp_private.LiveQr";
    static props = {...standardFieldProps};

    setup() {
        this.orm = useService("orm");
        this.state = useState({qr: false, status: "", detail: "", updatedAt: ""});
        this.stopped = false;
        onWillStart(() => this.refresh());
        onMounted(() => {
            this.timer = setInterval(() => this.refresh(), 2000);
        });
        onWillUnmount(() => {
            this.stopped = true;
            clearInterval(this.timer);
        });
    }

    get imageSource() {
        return this.state.qr ? `data:image/png;base64,${this.state.qr}` : false;
    }

    async refresh() {
        const recordId = this.props.record.resId;
        if (!recordId || this.loading) {
            return;
        }
        this.loading = true;
        try {
            const result = await this.orm.call(
                this.props.record.resModel,
                "get_whatsapp_private_live_qr",
                [[recordId]]
            );
            if (!this.stopped) {
                Object.assign(this.state, result);
            }
        } catch {
            // Keep the last valid QR visible during a transient RPC failure.
        } finally {
            this.loading = false;
        }
    }
}

registry.category("fields").add("whatsapp_private_live_qr", {
    component: WhatsAppPrivateLiveQr,
    supportedTypes: ["binary"],
});
