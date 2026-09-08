/** @odoo-module **/

import {Component, onWillUpdateProps, useState} from "@odoo/owl";
import {registry} from "@web/core/registry";
import {standardFieldProps} from "@web/views/fields/standard_field_props";
import {useService} from "@web/core/utils/hooks";

export class FlowerCalculatorImageFullscreen extends Component {
    static template = "flower_calculator.ImageFullscreen";
    static props = {...standardFieldProps};

    setup() {
        this.orm = useService("orm");
        this.state = useState({fullscreen: false, imageData: false});
        this.lastWriteDate = null;
        this.loadImage(this.props);
        onWillUpdateProps((nextProps) => this.loadImage(nextProps));
    }

    async loadImage(props) {
        const resId = props.record.resId;
        if (!resId) {
            this.lastWriteDate = null;
            this.state.imageData = false;
            return;
        }
        const writeDate = props.record.data.write_date;
        if (writeDate && writeDate === this.lastWriteDate) {
            return;
        }
        this.lastWriteDate = writeDate;
        // Fetched by RPC (POST, never cached by the browser or a service
        // worker) instead of the usual /web/image/... GET route, so a
        // freshly regenerated image always replaces the one shown here.
        const result = await this.orm.read(
            props.record.resModel,
            [resId],
            [props.name]
        );
        this.state.imageData = (result[0] && result[0][props.name]) || false;
    }

    get imageSource() {
        return this.state.imageData
            ? `data:image/png;base64,${this.state.imageData}`
            : false;
    }

    openFullscreen() {
        if (this.imageSource) {
            this.state.fullscreen = true;
        }
    }

    closeFullscreen() {
        this.state.fullscreen = false;
    }
}

registry.category("fields").add("flower_image_fullscreen", {
    component: FlowerCalculatorImageFullscreen,
    supportedTypes: ["binary"],
});
