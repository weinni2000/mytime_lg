import {Component, useState} from "@odoo/owl";

export class CampingMap extends Component {
    static template = "camping_map_booking.CampingMap";
    static props = {
        zones: Array,
        mapImageUrl: String,
    };

    setup() {
        this.state = useState({
            naturalWidth: 0,
            naturalHeight: 0,
            hoveredZoneId: null,
            selectedZoneId: null,
        });
    }

    get hoveredZone() {
        return this.props.zones.find((zone) => zone.id === this.state.hoveredZoneId);
    }

    get selectedZone() {
        return this.props.zones.find((zone) => zone.id === this.state.selectedZoneId);
    }

    onImageLoad(ev) {
        this.state.naturalWidth = ev.target.naturalWidth;
        this.state.naturalHeight = ev.target.naturalHeight;
    }

    onZoneHover(zoneId) {
        this.state.hoveredZoneId = zoneId;
    }

    onZoneClick(zoneId) {
        this.state.selectedZoneId = zoneId;
    }

    closePanel() {
        this.state.selectedZoneId = null;
    }

    zoneClass(zone) {
        const classes = ["o_camping_map_zone"];
        if (zone.id === this.state.hoveredZoneId) {
            classes.push("o_camping_map_zone_hover");
        }
        if (zone.id === this.state.selectedZoneId) {
            classes.push("o_camping_map_zone_selected");
        }
        return classes.join(" ");
    }
}
