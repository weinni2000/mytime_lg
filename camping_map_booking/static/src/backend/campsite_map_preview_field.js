import {Component, onWillUpdateProps, useState} from "@odoo/owl";
import {registry} from "@web/core/registry";
import {_t} from "@web/core/l10n/translation";
import {useService} from "@web/core/utils/hooks";
import {standardFieldProps} from "@web/views/fields/standard_field_props";
import {ResourceMap} from "@ressource_map/components/resource_map/resource_map";

export class CampsiteMapPreviewField extends Component {
    static template = "camping_map_booking.CampsiteMapPreviewField";
    static components = {ResourceMap};
    static props = {...standardFieldProps};

    setup() {
        this.orm = useService("orm");
        this.notification = useService("notification");
        this.state = useState({
            zones: [...(this.previewData.zones || [])],
            shapes: [...(this.previewData.shapes || [])],
            selectedZoneId: null,
            draftPoints: [],
            drawing: false,
        });
        onWillUpdateProps((nextProps) => {
            const data = nextProps.record.data[nextProps.name] || {};
            this.state.zones = [...(data.zones || [])];
            this.state.shapes = [...(data.shapes || [])];
        });
    }

    get previewData() {
        return this.props.record.data[this.props.name] || {};
    }

    get zones() {
        return this.state.shapes;
    }

    get mapImageUrl() {
        return this.previewData.image_url || "";
    }

    get legend() {
        return this.previewData.legend || [];
    }

    get legendPosition() {
        return this.previewData.legend_position || "none";
    }

    get draftPoints() {
        return this.state.draftPoints.map(({x, y}) => `${x},${y}`).join(" ");
    }

    get selectedZoneName() {
        const zone = this.state.zones.find(({id}) => id === this.state.selectedZoneId);
        return zone ? zone.name : "";
    }

    get labelScale() {
        return this.props.record.data.label_scale || 1;
    }

    onLabelScaleChange(ev) {
        // Persist on the record so the size survives a save and is shared with
        // the Testing tab; the form's dirty/save flow handles storing it.
        this.props.record.update({label_scale: Number(ev.target.value) || 1});
    }

    onZoneChange(ev) {
        const zoneId = Number(ev.target.value) || null;
        this.state.selectedZoneId = zoneId;
        this.state.draftPoints = [];
        this.state.drawing = false;
    }

    startNewPolygon() {
        // A polygon can only be drawn for a chosen zone.
        if (!this.state.selectedZoneId) {
            return;
        }
        this.state.drawing = true;
        this.state.draftPoints.splice(0);
    }

    parsePoints(points) {
        return points
            .split(/\s+/)
            .filter(Boolean)
            .map((point) => {
                const [x, y] = point.split(",").map(Number);
                return {x, y};
            })
            .filter(({x, y}) => Number.isFinite(x) && Number.isFinite(y));
    }

    addPoint(point) {
        if (this.state.drawing && this.state.selectedZoneId) {
            this.state.draftPoints.push(point);
        }
    }

    undoPoint() {
        this.state.draftPoints.pop();
    }

    clearPoints() {
        this.state.draftPoints.splice(0);
    }

    async saveZone() {
        const mapId = this.props.record.resId;
        if (!mapId) {
            this.notification.add(_t("Save the campsite map before marking a zone."), {
                type: "warning",
            });
            return;
        }
        if (!this.state.selectedZoneId || this.state.draftPoints.length < 3) {
            this.notification.add(_t("Select a zone and mark at least three points."), {
                type: "warning",
            });
            return;
        }
        const points = this.draftPoints;
        await this.orm.write("camping.map.zone", [this.state.selectedZoneId], {
            map_id: mapId,
            points,
        });
        const zone = this.state.zones.find(({id}) => id === this.state.selectedZoneId);
        this.state.shapes = this.state.shapes.filter(
            ({zone_id: zoneId}) => zoneId !== zone.id
        );
        this.state.shapes.push({
            id: `zone-${zone.id}`,
            zone_id: zone.id,
            name: zone.name,
            code: zone.code,
            symbol: zone.symbol,
            points,
            products: [],
            state: false,
        });
        this.clearPoints();
        this.state.drawing = false;
        this.notification.add(_t("The zone was saved."), {type: "success"});
    }

    async onCornersChanged(zoneId, points) {
        if (!zoneId || !points) {
            return;
        }
        await this.orm.write("camping.map.zone", [zoneId], {points});
        const shape = this.state.shapes.find(({zone_id: id}) => id === zoneId);
        if (shape) {
            shape.points = points;
        }
        this.notification.add(_t("The zone outline was updated."), {type: "success"});
    }

    async removeZone(zone) {
        await this.orm.write("camping.map.zone", [zone.zone_id], {points: false});
        this.state.shapes = this.state.shapes.filter(
            ({zone_id: zoneId}) => zoneId !== zone.zone_id
        );
        if (this.state.selectedZoneId === zone.zone_id) {
            this.clearPoints();
        }
        this.notification.add(_t("The zone outline was removed."), {type: "success"});
    }
}

registry.category("fields").add("campsite_map_preview", {
    component: CampsiteMapPreviewField,
    supportedTypes: ["json"],
});
