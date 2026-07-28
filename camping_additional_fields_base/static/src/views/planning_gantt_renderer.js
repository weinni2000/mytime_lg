/** @odoo-module **/

import {PlanningGanttRenderer} from "@planning/views/planning_gantt/planning_gantt_renderer";
import {patch} from "@web/core/utils/patch";

patch(PlanningGanttRenderer.prototype, {
    _usesGuestAggregation(pill) {
        return this._guestAggregation || Object.hasOwn(pill?.record || {}, "x_guests");
    },

    addTo(pill, group) {
        if (!this._usesGuestAggregation(pill)) {
            return super.addTo(...arguments);
        }
        this._guestAggregation = true;
        if (!pill.allocatedHours[group.col]) {
            return false;
        }
        group.pills.push(pill);
        group.aggregateValue += pill.record.x_guests || 0;
        return true;
    },

    getGroupPillDisplayName(pill) {
        if (!this._usesGuestAggregation(pill)) {
            return super.getGroupPillDisplayName(...arguments);
        }
        return String(pill.aggregateValue);
    },

    _computeDisplayName(pill) {
        if (this._usesGuestAggregation(pill)) {
            return pill.displayName;
        }
        return super._computeDisplayName(...arguments);
    },

    _computeResourceOvertimeColors(pill) {
        if (this._usesGuestAggregation(pill)) {
            return "bg-primary border-primary";
        }
        return super._computeResourceOvertimeColors(...arguments);
    },
});
