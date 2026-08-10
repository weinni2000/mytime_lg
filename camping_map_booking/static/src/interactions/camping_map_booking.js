import {registry} from "@web/core/registry";
import {Interaction} from "@web/public/interaction";
import {ResourceMap} from "@ressource_map/components/resource_map/resource_map";

export class CampingMapBooking extends Interaction {
    static selector = ".o_camping_map_booking";

    setup() {
        const zones = JSON.parse(this.el.dataset.zones || "[]");
        const mapImageUrl = this.el.dataset.mapImage;
        const mountEl = this.el.querySelector(".o_camping_map_mount");
        const selectable = this.el.dataset.selectable === "true";
        const selectedItemId = Number(this.el.dataset.selectedItem) || undefined;
        const legend = JSON.parse(this.el.dataset.legend || "[]");
        const legendPosition = this.el.dataset.legendPosition || "none";
        const props = {zones, mapImageUrl, selectedItemId, legend, legendPosition};
        if (selectable) {
            props.onSelectItem = (item) => {
                const input = document.getElementById(this.el.dataset.inputId);
                const button = document.getElementById(this.el.dataset.buttonId);
                const label = document.getElementById(this.el.dataset.labelId);
                if (input) {
                    input.value = item.id;
                }
                if (button) {
                    button.disabled = false;
                }
                if (label) {
                    label.textContent = item.name;
                }
            };
        }
        this.mountComponent(mountEl, ResourceMap, props);
    }
}

registry
    .category("public.interactions")
    .add("camping_map_booking.camping_map_booking", CampingMapBooking);
