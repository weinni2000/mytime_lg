import {registry} from "@web/core/registry";
import {Interaction} from "@web/public/interaction";
import {CampingMap} from "../components/camping_map/camping_map";

export class CampingMapBooking extends Interaction {
    static selector = ".o_camping_map_booking";

    setup() {
        const zones = JSON.parse(this.el.dataset.zones || "[]");
        const mapImageUrl = this.el.dataset.mapImage;
        const mountEl = this.el.querySelector(".o_camping_map_mount");
        this.mountComponent(mountEl, CampingMap, {zones, mapImageUrl});
    }
}

registry
    .category("public.interactions")
    .add("camping_map_booking.camping_map_booking", CampingMapBooking);
