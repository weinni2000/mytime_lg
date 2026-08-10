import {onWillStart, useState} from "@odoo/owl";
import {registry} from "@web/core/registry";
import {serializeDate, today} from "@web/core/l10n/dates";
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
        this.mapState = useState({
            imageUrl: false,
            night: serializeDate(today()),
            zones: [],
            legend: [],
            legendPosition: "none",
        });
        onWillStart(() => this.loadResourceMap());
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
        const previewData = await this.orm.call(
            "campsite.map",
            "get_gantt_map_preview",
            [],
            {night: this.mapState.night}
        );
        this.mapState.imageUrl = previewData.image_url || false;
        this.mapState.zones = previewData.shapes || [];
        this.mapState.legend = previewData.legend || [];
        this.mapState.legendPosition = previewData.legend_position || "none";
    }
}

export const ganttMapsView = {
    ...planningGanttView,
    type: "gantt_maps",
    ArchParser: GanttMapsArchParser,
    Renderer: GanttMapsRenderer,
};

registry.category("views").add("gantt_maps", ganttMapsView);
