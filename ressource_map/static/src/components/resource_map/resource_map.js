import {Component, onMounted, onWillUnmount, useRef, useState} from "@odoo/owl";

export class ResourceMap extends Component {
    static template = "ressource_map.ResourceMap";
    static props = {
        zones: Array,
        mapImageUrl: String,
        editable: {type: Boolean, optional: true},
        draftPoints: {type: String, optional: true},
        onMapClick: {type: Function, optional: true},
        onRemoveZone: {type: Function, optional: true},
        onCloseDraft: {type: Function, optional: true},
        onCornersChanged: {type: Function, optional: true},
        selectedItemId: {type: Number, optional: true},
        onSelectItem: {type: Function, optional: true},
        legend: {type: Array, optional: true},
        legendPosition: {type: String, optional: true},
    };

    setup() {
        this.mapImageRef = useRef("mapImage");
        this.updateAvailableHeight = () => {
            const image = this.mapImageRef.el;
            if (image) {
                // Target close to the full window height regardless of where the
                // image sits on the page - the page scrolls to reveal the rest.
                this.state.availableHeight = Math.max(120, window.innerHeight - 48);
                // Drives the legend size so it stays proportional to the map.
                this.state.mapWidth = image.getBoundingClientRect().width;
            }
        };
        this.state = useState({
            naturalWidth: 0,
            naturalHeight: 0,
            availableHeight: 0,
            mapWidth: 0,
            hoveredZoneId: null,
            selectedZoneId: null,
            selectedItemId: this.props.selectedItemId || null,
            // Corner-editing an existing zone (editor only).
            editZoneId: null,
            editPoints: [],
            draggingCorner: null,
        });
        onMounted(() => {
            this.updateAvailableHeight();
            window.addEventListener("resize", this.updateAvailableHeight);
        });
        onWillUnmount(() =>
            window.removeEventListener("resize", this.updateAvailableHeight)
        );
    }

    get isDrafting() {
        return Boolean(this.props.draftPoints);
    }

    get draftPointList() {
        return this.props.draftPoints
            ? this.props.draftPoints
                  .split(/\s+/)
                  .filter(Boolean)
                  .map((point) => point.split(",").map(Number))
            : [];
    }

    get draftStartPoint() {
        // The first point of the polygon being drawn — shown as a marker the
        // user can click to close and save the zone.
        return this.draftPointList[0];
    }

    onCloseDraftClick() {
        if (this.props.onCloseDraft) {
            this.props.onCloseDraft();
        }
    }

    get showLegend() {
        return Boolean(
            this.props.legend &&
                this.props.legend.length &&
                this.props.legendPosition &&
                this.props.legendPosition !== "none"
        );
    }

    get legendClass() {
        return `o_camping_map_legend o_camping_map_legend_${this.props.legendPosition}`;
    }

    get legendStyle() {
        // Scale the legend font with the rendered map width (everything else in
        // the legend is sized in em), so it stays proportional and never
        // dominates a small map. Clamped to keep it readable.
        const width = this.state.mapWidth;
        if (!width) {
            return undefined;
        }
        const fontPx = Math.max(9, Math.min(14, width * 0.03));
        return `font-size: ${fontPx}px`;
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
        this.updateAvailableHeight();
    }

    onZoneHover(zoneId) {
        this.state.hoveredZoneId = zoneId;
    }

    onZoneClick(zone, ev) {
        if (this.props.editable) {
            // In the editor, click an existing zone (with an outline) to edit
            // its corners — unless a new polygon is currently being drawn.
            if (this.props.onCornersChanged && !this.isDrafting && zone.points) {
                if (ev) {
                    ev.stopPropagation();
                }
                this.startCornerEdit(zone);
            }
            return;
        }
        if (this.props.onSelectItem) {
            const item = zone.products.find((product) => product.selectable);
            if (item) {
                this.onItemClick(item);
            }
            return;
        }
        this.state.selectedZoneId = zone.zone_id;
    }

    startCornerEdit(zone) {
        this.state.editZoneId = zone.zone_id;
        this.state.editPoints = this.zonePoints(zone);
        this.state.draggingCorner = null;
    }

    isEditingZone(zone) {
        return (
            zone.zone_id === this.state.editZoneId && this.state.editPoints.length > 0
        );
    }

    zonePointsString(zone) {
        if (this.isEditingZone(zone)) {
            return this.state.editPoints.map((point) => point.join(",")).join(" ");
        }
        return zone.points;
    }

    eventToImageCoords(ev) {
        const image = this.mapImageRef.el;
        if (!image) {
            return null;
        }
        const bounds = image.getBoundingClientRect();
        return [
            Math.round(
                ((ev.clientX - bounds.left) / bounds.width) * this.state.naturalWidth
            ),
            Math.round(
                ((ev.clientY - bounds.top) / bounds.height) * this.state.naturalHeight
            ),
        ];
    }

    _saveCorners() {
        if (this.props.onCornersChanged) {
            this.props.onCornersChanged(
                this.state.editZoneId,
                this.state.editPoints.map((point) => point.join(",")).join(" ")
            );
        }
    }

    onCornerPointerDown(index, ev) {
        ev.stopPropagation();
        ev.target.setPointerCapture(ev.pointerId);
        this.state.draggingCorner = index;
        this.cornerDragged = false;
    }

    onCornerPointerMove(index, ev) {
        if (this.state.draggingCorner !== index) {
            return;
        }
        const coords = this.eventToImageCoords(ev);
        if (coords) {
            this.state.editPoints[index] = coords;
            this.cornerDragged = true;
        }
    }

    onCornerPointerUp(index, ev) {
        if (this.state.draggingCorner !== index) {
            return;
        }
        ev.target.releasePointerCapture(ev.pointerId);
        this.state.draggingCorner = null;
        // Only persist when the corner actually moved (ignore plain clicks and
        // the click pair of a double-click that removes a corner).
        if (this.cornerDragged) {
            this._saveCorners();
        }
    }

    removeCorner(index, ev) {
        if (ev) {
            ev.stopPropagation();
        }
        // A polygon needs at least three corners.
        if (this.state.editPoints.length <= 3) {
            return;
        }
        this.state.editPoints.splice(index, 1);
        this._saveCorners();
    }

    insertCorner(index, ev) {
        ev.stopPropagation();
        const coords = this.eventToImageCoords(ev);
        if (!coords) {
            return;
        }
        // Add a corner on the clicked edge, between its two endpoints.
        this.state.editPoints.splice(index + 1, 0, coords);
        this._saveCorners();
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

    onItemClick(item) {
        if (!item.selectable || !this.props.onSelectItem) {
            return;
        }
        this.state.selectedItemId = item.id;
        this.props.onSelectItem(item);
    }

    itemClass(item) {
        const classes = ["o_camping_map_pitch", "btn", "w-100", "text-start"];
        classes.push(
            item.id === this.state.selectedItemId
                ? "btn-primary"
                : "btn-outline-secondary"
        );
        return classes.join(" ");
    }

    itemStateLabel(item) {
        // Label comes from the camping.map.state model (see _get_frontend_map);
        // the map below is only a fallback when no label was provided.
        return (
            item.state_label ||
            {
                free: "Free",
                occupied: "Occupied",
                not_suitable: "Not suitable",
            }[item.state] ||
            ""
        );
    }

    closePanel() {
        this.state.selectedZoneId = null;
    }

    zoneClass(zone) {
        const classes = ["o_camping_map_zone"];
        if (zone.state) {
            classes.push(`o_camping_map_zone_state_${zone.state}`);
        }
        if (
            this.state.selectedItemId &&
            !zone.products.some((item) => item.id === this.state.selectedItemId)
        ) {
            classes.push("o_camping_map_zone_muted");
        }
        if (zone.id === this.state.hoveredZoneId) {
            classes.push("o_camping_map_zone_hover");
        }
        if (zone.zone_id === this.state.selectedZoneId) {
            classes.push("o_camping_map_zone_selected");
        }
        if (this.isEditingZone(zone)) {
            classes.push("o_camping_map_zone_editing");
        }
        return classes.join(" ");
    }

    zoneStyle(zone) {
        // Feed the zone's availability colors (from the camping.map.state model)
        // into CSS custom properties so the SCSS renders straight from them.
        const colors = zone.colors;
        if (!colors) {
            return undefined;
        }
        const vars = [];
        if (colors.fill) {
            vars.push(`--o-zone-fill: ${colors.fill}`);
        }
        if (colors.stroke) {
            vars.push(`--o-zone-stroke: ${colors.stroke}`);
        }
        if (colors.hover) {
            vars.push(`--o-zone-hover: ${colors.hover}`);
        }
        return vars.length ? vars.join("; ") : undefined;
    }
}
