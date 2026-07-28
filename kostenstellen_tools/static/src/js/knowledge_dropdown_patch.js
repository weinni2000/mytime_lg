/** @odoo-module **/

import {Dropdown} from "@web/core/dropdown/dropdown";
import {patch} from "@web/core/utils/patch";

patch(Dropdown.prototype, {
    popoverCloseOnClickAway(target) {
        if (!target || !this.activeEl) {
            return true;
        }
        return super.popoverCloseOnClickAway(target);
    },
});
