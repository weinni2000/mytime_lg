/** @odoo-module **/

import {registry} from "@web/core/registry";
import {KanbanHeader} from "@web/views/kanban/kanban_header";
import {KanbanRenderer} from "@web/views/kanban/kanban_renderer";
import {kanbanView} from "@web/views/kanban/kanban_view";

export class BookingKanbanWeekdayHeader extends KanbanHeader {
    static template = "booking_engine_kanban_weekday.KanbanHeader";

    get weekdayDisplayName() {
        const {displayName, groupByField, range, value} = this.group;
        const isDailyDateGroup =
            ["date", "datetime"].includes(groupByField.type) &&
            range?.to?.diff(range.from, "days").days === 1;
        if (!isDailyDateGroup || !value?.toFormat) {
            return displayName;
        }
        const weekday = value.toFormat("ccc").replace(/\.$/, "");
        return `${displayName} ${weekday}`;
    }
}

export class BookingKanbanWeekdayRenderer extends KanbanRenderer {
    static components = {
        ...KanbanRenderer.components,
        KanbanHeader: BookingKanbanWeekdayHeader,
    };
}

registry.category("views").add("booking_engine_kanban_weekday", {
    ...kanbanView,
    Renderer: BookingKanbanWeekdayRenderer,
});
