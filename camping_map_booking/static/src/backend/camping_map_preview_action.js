import {Component, onWillStart, useState} from "@odoo/owl";
import {registry} from "@web/core/registry";
import {useService} from "@web/core/utils/hooks";
import {CampingMap} from "../components/camping_map/camping_map";

export class CampingMapPreviewAction extends Component {
    static template = "camping_map_booking.CampingMapPreviewAction";
    static components = {CampingMap};
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.state = useState({zones: []});
        onWillStart(async () => {
            const zones = await this.orm.searchRead(
                "camping.map.zone",
                [],
                ["name", "points"]
            );
            this.state.zones = zones.map((zone) => ({...zone, products: []}));
        });
    }
}

registry
    .category("actions")
    .add("camping_map_booking.map_preview_action", CampingMapPreviewAction);
