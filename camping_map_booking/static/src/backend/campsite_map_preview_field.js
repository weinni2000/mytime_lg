import {Component, onWillUpdateProps, useState} from "@odoo/owl";
import {registry} from "@web/core/registry";
import {_t} from "@web/core/l10n/translation";
import {useService} from "@web/core/utils/hooks";
import {standardFieldProps} from "@web/views/fields/standard_field_props";
import {CampingMap} from "../components/camping_map/camping_map";

export class CampsiteMapPreviewField extends Component {
    static template = "camping_map_booking.CampsiteMapPreviewField";
    static components = {CampingMap};
    static props = {...standardFieldProps};

    setup() {
        this.orm = useService("orm");
        this.notification = useService("notification");
        this.state = useState({
            zones: [...(this.previewData.zones || [])],
            shapes: [...(this.previewData.shapes || [])],
            selectedZoneId: null,
            draftPoints: [],
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

    get draftPoints() {
        return this.state.draftPoints.map(({x, y}) => `${x},${y}`).join(" ");
    }

    onZoneChange(ev) {
        const zoneId = Number(ev.target.value) || null;
        this.state.selectedZoneId = zoneId;
        this.state.draftPoints = [];
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
        if (this.state.selectedZoneId) {
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
        this.notification.add(_t("The zone was saved."), {type: "success"});
    }
}

registry.category("fields").add("campsite_map_preview", {
    component: CampsiteMapPreviewField,
    supportedTypes: ["json"],
});
