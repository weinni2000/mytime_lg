import {Component, useState} from "@odoo/owl";

export class CampingMap extends Component {
    static template = "camping_map_booking.CampingMap";
    static props = {
        zones: Array,
        mapImageUrl: String,
        editable: {type: Boolean, optional: true},
        draftPoints: {type: String, optional: true},
        onMapClick: {type: Function, optional: true},
        onRemoveZone: {type: Function, optional: true},
    };

    setup() {
        this.state = useState({
            naturalWidth: 0,
            naturalHeight: 0,
            hoveredZoneId: null,
            selectedZoneId: null,
        });
    }

    get isDrafting() {
        return Boolean(this.props.draftPoints);
    }

    get hoveredZone() {
        return this.props.zones.find((zone) => zone.id === this.state.hoveredZoneId);
    }

    get selectedZone() {
        return this.props.zones.find(
            (zone) => zone.zone_id === this.state.selectedZoneId
        );
    }

    onImageLoad(ev) {
        this.state.naturalWidth = ev.target.naturalWidth;
        this.state.naturalHeight = ev.target.naturalHeight;
    }

    onZoneHover(zoneId) {
        this.state.hoveredZoneId = zoneId;
    }

    onZoneClick(zone) {
        if (this.props.editable) {
            return;
        }
        this.state.selectedZoneId = zone.zone_id;
    }

    onMapClick(ev) {
        if (!this.props.editable || !this.props.onMapClick) {
            return;
        }
        const bounds = ev.currentTarget.getBoundingClientRect();
        this.props.onMapClick({
            x: Math.round(
                ((ev.clientX - bounds.left) / bounds.width) * this.state.naturalWidth
            ),
            y: Math.round(
                ((ev.clientY - bounds.top) / bounds.height) * this.state.naturalHeight
            ),
        });
    }

    zonePoints(zone) {
        return zone.points
            .split(/\s+/)
            .filter(Boolean)
            .map((point) => point.split(",").map(Number));
    }

    zoneLabelPosition(zone) {
        const points = this.zonePoints(zone);
        const total = points.reduce(
            (position, [x, y]) => ({
                x: position.x + x,
                y: position.y + y,
            }),
            {x: 0, y: 0}
        );
        return {x: total.x / points.length, y: total.y / points.length};
    }

    zoneTopRight(zone) {
        const points = this.zonePoints(zone);
        return {
            x: Math.max(...points.map(([x]) => x)),
            y: Math.min(...points.map(([, y]) => y)),
        };
    }

    onRemoveZoneClick(zone) {
        if (this.props.onRemoveZone) {
            this.props.onRemoveZone(zone);
        }
    }

    closePanel() {
        this.state.selectedZoneId = null;
    }

    zoneClass(zone) {
        const classes = ["o_camping_map_zone"];
        if (zone.state) {
            classes.push(`o_camping_map_zone_state_${zone.state}`);
        }
        if (zone.id === this.state.hoveredZoneId) {
            classes.push("o_camping_map_zone_hover");
        }
        if (zone.zone_id === this.state.selectedZoneId) {
            classes.push("o_camping_map_zone_selected");
        }
        return classes.join(" ");
    }
}
