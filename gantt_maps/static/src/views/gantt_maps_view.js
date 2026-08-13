import {onWillStart, useState} from "@odoo/owl";
import {registry} from "@web/core/registry";
import {useBus} from "@web/core/utils/hooks";
import {serializeDate, serializeDateTime, today} from "@web/core/l10n/dates";

// Luxon is exposed as a global in the Odoo asset bundle (not an ES module).
const {DateTime} = luxon;
import {parseXML, serializeXML} from "@web/core/utils/xml";
import {planningGanttView} from "@planning/views/planning_gantt/planning_gantt_view";
import {ResourceMap} from "@ressource_map/components/resource_map/resource_map";

class GanttMapsArchParser extends planningGanttView.ArchParser {
    parse(arch) {
        const serializedArch = serializeXML(arch)
            .replace(/<gantt_maps\b/, "<gantt")
            .replace(/<\/gantt_maps>/, "</gantt>");
        return super.parse(parseXML(serializedArch));
    }
}

class GanttMapsRenderer extends planningGanttView.Renderer {
    static template = "gantt_maps.GanttMapsRenderer";
    static components = {...planningGanttView.Renderer.components, ResourceMap};

    setup() {
        super.setup();
        const now = today();
        this.mapState = useState({
            imageUrl: false,
            // "night" = a single point in time, "range" = a stay across nights.
            mode: "night",
            // Local "yyyy-MM-ddTHH:mm" for the datetime-local input.
            point: DateTime.local().toFormat("yyyy-MM-dd'T'HH:mm"),
            rangeStart: serializeDate(now),
            rangeEnd: serializeDate(now.plus({days: 1})),
            // In range mode the dates follow the Gantt's visible window unless
            // the user opts to type them in by hand.
            manualRange: false,
            // Also paint the unallocated (free) share of each pitch white.
            showFree: false,
            // Blow the map panel up to cover the whole viewport.
            fullscreen: false,
            zones: [],
            legend: [],
            legendPosition: "none",
            labelScale: 1,
        });
        // Keep the range in step with the Gantt as the user navigates/zooms it.
        useBus(this.model.bus, "update", () => this.syncGanttRange());
        onWillStart(() => this.loadResourceMap());
    }

    get ganttRange() {
        // The Gantt's visible window. stopDate is the last visible day
        // (inclusive), so check-out is the day after to include it as a night.
        const {startDate, stopDate} = this.model.metaData;
        return {
            start: serializeDate(startDate),
            end: serializeDate(stopDate.plus({days: 1})),
        };
    }

    syncGanttRange() {
        if (this.mapState.mode !== "range" || this.mapState.manualRange) {
            return;
        }
        const {start, end} = this.ganttRange;
        if (start !== this.mapState.rangeStart || end !== this.mapState.rangeEnd) {
            this.mapState.rangeStart = start;
            this.mapState.rangeEnd = end;
            this.loadResourceMap();
        }
    }

    onModeChange() {
        // Entering range mode picks up the current Gantt window straight away.
        if (this.mapState.mode === "range" && !this.mapState.manualRange) {
            const {start, end} = this.ganttRange;
            this.mapState.rangeStart = start;
            this.mapState.rangeEnd = end;
        }
        this.loadResourceMap();
    }

    toggleFullscreen() {
        this.mapState.fullscreen = !this.mapState.fullscreen;
    }

    toggleManualRange() {
        this.mapState.manualRange = !this.mapState.manualRange;
        // Switching back to automatic re-aligns with the Gantt window.
        if (!this.mapState.manualRange) {
            this.syncGanttRange();
        }
    }

    async dragPillDrop(params) {
        await super.dragPillDrop(params);
        await this.loadResourceMap();
    }

    async resizePillDrop(params) {
        await super.resizePillDrop(params);
        await this.loadResourceMap();
    }

    async loadResourceMap() {
        const isRange = this.mapState.mode === "range";
        // Point in time: convert the local datetime-local value to a server
        // (UTC) datetime; date range: pass the two dates.
        const start = isRange
            ? this.mapState.rangeStart
            : serializeDateTime(DateTime.fromISO(this.mapState.point));
        const end = isRange ? this.mapState.rangeEnd : null;
        const previewData = await this.orm.call(
            "campsite.map",
            "get_gantt_map_preview",
            [start, end, this.mapState.showFree]
        );
        this.mapState.imageUrl = previewData.image_url || false;
        this.mapState.zones = previewData.shapes || [];
        this.mapState.legend = previewData.legend || [];
        this.mapState.legendPosition = previewData.legend_position || "none";
        this.mapState.labelScale = previewData.label_scale || 1;
    }
}

export const ganttMapsView = {
    ...planningGanttView,
    type: "gantt_maps",
    ArchParser: GanttMapsArchParser,
    Renderer: GanttMapsRenderer,
};

registry.category("views").add("gantt_maps", ganttMapsView);
