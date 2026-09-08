/** @odoo-module **/

import {BankRecButtonList} from "@account_accountant/components/bank_reconciliation/button_list/button_list";
import {patch} from "@web/core/utils/patch";

patch(BankRecButtonList.prototype, {
    async searchInvoiceInMail() {
        const action = await this.orm.call(
            "account.bank.statement.line",
            "action_search_invoice_in_mail",
            [this.statementLineData.id]
        );
        this.props.statementLine.load();
        this.bankReconciliation.reloadChatter();
        if (action) {
            this.action.doAction(action);
        }
        this.restoreFocus();
    },
});
