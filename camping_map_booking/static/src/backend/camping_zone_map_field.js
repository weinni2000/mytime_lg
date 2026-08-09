import {Component} from "@odoo/owl";
import {registry} from "@web/core/registry";
import {standardFieldProps} from "@web/views/fields/standard_field_props";
import {CampingMap} from "../components/camping_map/camping_map";

export class CampingZoneMapField extends Component {
    static template = "camping_map_booking.CampingZoneMapField";
    static components = {CampingMap};
    static props = {...standardFieldProps};

    // Read straight from the record (reactive) rather than caching in local
    // state, so the map recolors when the tested vehicle / stay recomputes the
    // JSON value. Copying to state only refreshed via onWillUpdateProps, which
    // left the polygons frozen on the previously selected vehicle.
    get previewData() {
        return this.props.record.data[this.props.name] || {};
    }

    get shapes() {
        return this.previewData.shapes || [];
    }

    get mapImageUrl() {
        return this.previewData.image_url || "";
    }
}

registry.category("fields").add("camping_zone_map", {
    component: CampingZoneMapField,
    supportedTypes: ["json"],
});
