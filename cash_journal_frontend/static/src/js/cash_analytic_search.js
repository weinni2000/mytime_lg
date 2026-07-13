(function () {
    function setVisible(element, visible) {
        if (!element) {
            return;
        }
        element.classList.toggle("d-none", !visible);
    }

    function setStatus(element, message) {
        if (!element) {
            return;
        }
        element.textContent = message || "";
        setVisible(element, Boolean(message));
    }

    function selectFirstRemoteOption(
        control,
        displayInput,
        statusElement,
        config,
        planSelect,
        companySelect
    ) {
        const body = new FormData();
        body.append("term", "");
        body.append("limit", "1");
        const select = control.input;
        const planId =
            (select && select.dataset.cashAnalyticPlanId) ||
            (planSelect && planSelect.value);
        if (planId) {
            body.append("plan_id", planId);
        }
        if (companySelect && companySelect.value) {
            body.append("company_id", companySelect.value);
        }
        setStatus(statusElement, "Loading default...");
        fetch(config.url, {
            method: "POST",
            body,
            credentials: "same-origin",
        })
            .then((response) => response.json())
            .then((payload) => {
                const firstOption = (payload.results || [])[0];
                if (!firstOption) {
                    setStatus(statusElement, "No analytic account found.");
                    return;
                }
                control.addOption(firstOption);
                control.setValue(firstOption.id, true);
                displayInput.value = firstOption.label;
                setStatus(statusElement, "");
                if (config.onValueChange) {
                    config.onValueChange();
                }
            })
            .catch(() => setStatus(statusElement, "Search failed."));
    }

    function applyLineDefaults(lineElement, distributionJson, displayText) {
        const distributionInput = lineElement.querySelector(
            "[data-cash-line-distribution]"
        );
        const displayInput = lineElement.querySelector(
            "[data-cash-line-distribution-display]"
        );
        const summaryElement = lineElement.querySelector(
            "[data-cash-distribution-summary]"
        );
        if (distributionInput) {
            distributionInput.value = distributionJson;
            distributionInput.setAttribute("value", distributionJson);
        }
        if (displayInput) {
            displayInput.value = displayText;
            displayInput.setAttribute("value", displayText);
        }
        if (summaryElement) {
            summaryElement.textContent = displayText;
        }
    }

    function refreshLineDefaults() {
        const rootElement = document.querySelector("[data-cash-lines]");
        const form = rootElement && rootElement.closest("form");
        if (!rootElement || !form) {
            return;
        }

        const manualDistributionSelect = form.querySelector(
            "[name='manual_distribution_id']"
        );
        const analyticAccountSelect = form.querySelector("#cash_analytic_account");
        const companySelect = form.querySelector("[name='company_id']");

        const body = new FormData();
        if (manualDistributionSelect && manualDistributionSelect.value) {
            body.append("manual_distribution_id", manualDistributionSelect.value);
        }
        if (analyticAccountSelect && analyticAccountSelect.value) {
            body.append("analytic_account_id", analyticAccountSelect.value);
        }
        if (companySelect && companySelect.value) {
            body.append("company_id", companySelect.value);
        }

        fetch("/cash/analytic_distribution/default", {
            method: "POST",
            body,
            credentials: "same-origin",
        })
            .then((response) => (response.ok ? response.json() : null))
            .then((payload) => {
                if (!payload) {
                    return;
                }
                const distributionJson = JSON.stringify(payload.distribution || {});
                const displayText = payload.display || "";

                rootElement
                    .querySelectorAll("[data-cash-line]")
                    .forEach((lineElement) => {
                        if (lineElement.dataset.cashLineDirty === "1") {
                            return;
                        }
                        applyLineDefaults(lineElement, distributionJson, displayText);
                    });

                const lineTemplate = rootElement.querySelector(
                    "[data-cash-line-template]"
                );
                if (lineTemplate) {
                    applyLineDefaults(
                        lineTemplate.content,
                        distributionJson,
                        displayText
                    );
                }
            })
            .catch(() => undefined);
    }

    function buildTomSelectConfig(
        select,
        planSelect,
        companySelect,
        statusElement,
        displayInput,
        config
    ) {
        const tomSelectConfig = {
            valueField: "id",
            labelField: "label",
            searchField: "label",
            maxItems: 1,
            create: false,
            allowEmptyOption: Boolean(config.allowEmptyOption),
            preload: false,
            loadThrottle: 250,
            placeholder: config.placeholder,
            render: {
                no_results: function () {
                    return `<div class="no-results">${config.noResults}</div>`;
                },
            },
            load: function (query, callback) {
                const term = (query || "").trim();
                if (!term && !config.allowEmptySearch) {
                    callback();
                    return;
                }

                const body = new FormData();
                body.append("term", term);
                body.append("limit", "20");
                const planId =
                    select.dataset.cashAnalyticPlanId ||
                    (planSelect && planSelect.value);
                if (config.usePlan && planId) {
                    body.append("plan_id", planId);
                }
                if (companySelect && companySelect.value) {
                    body.append("company_id", companySelect.value);
                }

                setStatus(statusElement, "Searching...");
                fetch(config.url, {
                    method: "POST",
                    body,
                    credentials: "same-origin",
                })
                    .then((response) =>
                        response.json().then((payload) => ({
                            ok: response.ok,
                            payload,
                        }))
                    )
                    .then((result) => {
                        if (!result.ok) {
                            setStatus(
                                statusElement,
                                result.payload.error || "Search failed."
                            );
                            callback();
                            return;
                        }
                        setStatus(statusElement, "");
                        callback(result.payload.results || []);
                    })
                    .catch(() => {
                        setStatus(statusElement, "Search failed.");
                        callback();
                    });
            },
            onChange: function (value) {
                if (!value) {
                    displayInput.value = "";
                    if (config.onValueChange) {
                        config.onValueChange();
                    }
                    return;
                }
                const option = this.options[value];
                displayInput.value = option ? option.label : "";
                if (config.onValueChange) {
                    config.onValueChange();
                }
            },
            onType: function () {
                if (this.getValue()) {
                    this.clear(true);
                    displayInput.value = "";
                }
            },
        };
        if (config.removeButton) {
            tomSelectConfig.plugins = {
                remove_button: {
                    title: config.removeButtonTitle || "Remove",
                },
            };
        }
        return tomSelectConfig;
    }

    function applyInitialSelectValue(select, control, displayInput) {
        if (select.value && select.options.length) {
            displayInput.value =
                select.options[select.selectedIndex].textContent.trim();
        } else if (displayInput.value) {
            control.control_input.value = displayInput.value;
        }
    }

    function attachAutoSelectListener(
        sourceSelect,
        control,
        displayInput,
        statusElement,
        config,
        planSelect,
        companySelect,
        shouldSelectFirst
    ) {
        sourceSelect.addEventListener("change", () => {
            control.clear(true);
            control.clearOptions();
            displayInput.value = "";
            setStatus(statusElement, "");
            if (shouldSelectFirst) {
                selectFirstRemoteOption(
                    control,
                    displayInput,
                    statusElement,
                    config,
                    planSelect,
                    companySelect
                );
            }
        });
    }

    function initializeRemoteSelect(rootElement, config) {
        if (rootElement.dataset.cashTomSelectReady) {
            return;
        }
        rootElement.dataset.cashTomSelectReady = "1";

        const form = rootElement.closest("form");
        const select = rootElement.querySelector(config.selectSelector);
        const displayInput = rootElement.querySelector(config.displaySelector);
        const statusElement = rootElement.querySelector(config.statusSelector);
        const planSelect = form
            ? form.querySelector("[name='analytic_plan_id']")
            : null;
        const companySelect = form ? form.querySelector("[name='company_id']") : null;
        if ([form, select, displayInput, statusElement].some((element) => !element)) {
            return;
        }

        if (!window.TomSelect) {
            setStatus(
                statusElement,
                "Tom Select could not be loaded. Check CDN access."
            );
            return;
        }

        const tomSelectConfig = buildTomSelectConfig(
            select,
            planSelect,
            companySelect,
            statusElement,
            displayInput,
            config
        );
        const control = new window.TomSelect(select, tomSelectConfig);

        applyInitialSelectValue(select, control, displayInput);

        if (config.usePlan && planSelect && !select.dataset.cashAnalyticPlanId) {
            attachAutoSelectListener(
                planSelect,
                control,
                displayInput,
                statusElement,
                config,
                planSelect,
                companySelect,
                config.selectFirstOnPlanChange
            );
        }
        if (companySelect) {
            attachAutoSelectListener(
                companySelect,
                control,
                displayInput,
                statusElement,
                config,
                planSelect,
                companySelect,
                config.selectFirstOnCompanyChange
            );
        }
    }

    function initializeAnalyticSearch(rootElement) {
        initializeRemoteSelect(rootElement, {
            selectSelector: "[data-cash-analytic-select]",
            displaySelector: "[data-cash-analytic-display]",
            statusSelector: "[data-cash-analytic-status]",
            placeholder: "Search with text or regex",
            noResults: "No analytic account found",
            url: "/cash/analytic_accounts/search",
            usePlan: true,
            allowEmptyOption: false,
            allowEmptySearch: true,
            selectFirstOnPlanChange: true,
            selectFirstOnCompanyChange: true,
            removeButton: true,
            removeButtonTitle: "Remove analytic account",
            onValueChange: rootElement.dataset.cashAnalyticDefault
                ? refreshLineDefaults
                : undefined,
        });
    }

    function initializePartnerSearch(rootElement) {
        initializeRemoteSelect(rootElement, {
            selectSelector: "[data-cash-partner-select]",
            displaySelector: "[data-cash-partner-display]",
            statusSelector: "[data-cash-partner-status]",
            placeholder: "Search existing partners",
            noResults: "No partner found",
            url: "/cash/partners/search",
            usePlan: false,
            allowEmptyOption: true,
            allowEmptySearch: false,
            selectFirstOnPlanChange: false,
            selectFirstOnCompanyChange: false,
        });
    }

    function updateLineRemoveButtons(rootElement) {
        const lineElements = rootElement.querySelectorAll("[data-cash-line]");
        lineElements.forEach((lineElement) => {
            const removeButton = lineElement.querySelector("[data-cash-line-remove]");
            if (removeButton) {
                removeButton.disabled = lineElements.length <= 1;
            }
        });
    }

    function getDistributionModal(rootElement) {
        return rootElement.querySelector("[data-cash-distribution-modal]");
    }

    function showModal(modalElement) {
        if (window.Modal) {
            window.Modal.getOrCreateInstance(modalElement).show();
            return;
        }
        modalElement.classList.add("show");
        modalElement.style.display = "block";
        modalElement.removeAttribute("aria-hidden");
    }

    function hideModal(modalElement) {
        if (window.Modal) {
            window.Modal.getOrCreateInstance(modalElement).hide();
            return;
        }
        modalElement.classList.remove("show");
        modalElement.style.display = "none";
        modalElement.setAttribute("aria-hidden", "true");
    }

    function parseDistribution(distributionValue) {
        try {
            const distribution = JSON.parse(distributionValue || "{}");
            return distribution &&
                typeof distribution === "object" &&
                !Array.isArray(distribution)
                ? distribution
                : {};
        } catch {
            return {};
        }
    }

    function getDistributionPercentage(distributionValue) {
        if (distributionValue && typeof distributionValue === "object") {
            return Number(distributionValue.percentage || 0);
        }
        return Number(distributionValue || 0);
    }

    function getDistributionLabel(analyticAccountId, distributionValue, fallbackLabel) {
        if (
            distributionValue &&
            typeof distributionValue === "object" &&
            distributionValue.label
        ) {
            return distributionValue.label;
        }
        return fallbackLabel || `Analytic account ${analyticAccountId}`;
    }

    function getDistributionAccounts(
        analyticAccountKey,
        distributionValue,
        fallbackLabel
    ) {
        if (
            distributionValue &&
            typeof distributionValue === "object" &&
            Array.isArray(distributionValue.accounts)
        ) {
            return distributionValue.accounts;
        }
        return String(analyticAccountKey || "")
            .split(",")
            .filter(Boolean)
            .map((analyticAccountId) => ({
                id: analyticAccountId,
                label: getDistributionLabel(
                    analyticAccountId,
                    distributionValue,
                    fallbackLabel
                ),
            }));
    }

    function updateDistributionTotal(modalElement) {
        const totalElement = modalElement.querySelector(
            "[data-cash-distribution-total]"
        );
        const total = Array.from(
            modalElement.querySelectorAll("[data-cash-distribution-percentage]")
        ).reduce((sum, input) => sum + Number(input.value || 0), 0);
        if (totalElement) {
            totalElement.textContent = total.toFixed(2).replace(/\.?0+$/, "");
            totalElement.classList.toggle(
                "text-danger",
                Math.abs(total - 100) > 0.0001
            );
        }
    }

    function setDistributionError(modalElement, message) {
        const errorElement = modalElement.querySelector(
            "[data-cash-distribution-error]"
        );
        if (!errorElement) {
            return;
        }
        errorElement.textContent = message || "";
        setVisible(errorElement, Boolean(message));
    }

    function addDistributionRow(modalElement, accounts, percentage) {
        const rowTemplate = modalElement.parentElement.querySelector(
            "[data-cash-distribution-row-template]"
        );
        const rowList = modalElement.querySelector("[data-cash-distribution-list]");
        if (!rowTemplate || !rowList) {
            return;
        }
        const rowElement = rowTemplate.content.firstElementChild.cloneNode(true);
        const percentageInput = rowElement.querySelector(
            "[data-cash-distribution-percentage]"
        );

        rowList.appendChild(rowElement);
        if (percentageInput) {
            percentageInput.value = percentage || 100;
        }
        rowElement
            .querySelectorAll("[data-cash-analytic-search]")
            .forEach(initializeAnalyticSearch);
        (accounts || []).forEach((account) => {
            const select = account.plan_id
                ? rowElement.querySelector(
                      `[data-cash-analytic-select][data-cash-analytic-plan-id="${account.plan_id}"]`
                  )
                : rowElement.querySelector("[data-cash-analytic-select]:not([value])");
            if (!select || !select.tomselect) {
                return;
            }
            const option = {
                id: String(account.id),
                label: account.label || `Analytic account ${account.id}`,
                plan_id: account.plan_id,
            };
            const displayInput = select
                .closest("[data-cash-analytic-search]")
                .querySelector("[data-cash-analytic-display]");
            select.tomselect.addOption(option);
            select.tomselect.setValue(option.id, true);
            if (displayInput) {
                displayInput.value = option.label;
            }
        });
        updateDistributionTotal(modalElement);
    }

    function openDistributionModal(rootElement, lineElement) {
        const modalElement = getDistributionModal(rootElement);
        if (!modalElement) {
            return;
        }
        const rowList = modalElement.querySelector("[data-cash-distribution-list]");
        const distributionInput = lineElement.querySelector(
            "[data-cash-line-distribution]"
        );
        const displayInput = lineElement.querySelector(
            "[data-cash-line-distribution-display]"
        );
        if (!rowList || !distributionInput || !displayInput) {
            return;
        }

        modalElement.cashCurrentLine = lineElement;
        rowList.innerHTML = "";
        setDistributionError(modalElement, "");

        const distribution = parseDistribution(distributionInput.value);
        const entries = Object.entries(distribution);
        if (entries.length) {
            entries.forEach(([analyticAccountId, distributionValue]) => {
                addDistributionRow(
                    modalElement,
                    getDistributionAccounts(
                        analyticAccountId,
                        distributionValue,
                        displayInput.value
                    ),
                    getDistributionPercentage(distributionValue)
                );
            });
        } else {
            addDistributionRow(modalElement, [], 100);
        }
        showModal(modalElement);
    }

    function saveDistributionModal(modalElement) {
        const lineElement = modalElement.cashCurrentLine;
        if (!lineElement) {
            hideModal(modalElement);
            return;
        }

        const distribution = {};
        const summaries = [];
        let total = 0;
        for (const rowElement of modalElement.querySelectorAll(
            "[data-cash-distribution-row]"
        )) {
            const percentageInput = rowElement.querySelector(
                "[data-cash-distribution-percentage]"
            );
            const percentage = Number((percentageInput && percentageInput.value) || 0);
            const selectedAccounts = Array.from(
                rowElement.querySelectorAll("[data-cash-analytic-select]")
            )
                .map((select) => {
                    const analyticAccountId =
                        select && select.tomselect
                            ? select.tomselect.getValue()
                            : select.value;
                    if (!analyticAccountId) {
                        return false;
                    }
                    const displayInput = select
                        .closest("[data-cash-analytic-search]")
                        .querySelector("[data-cash-analytic-display]");
                    return {
                        id: String(analyticAccountId),
                        label: (displayInput && displayInput.value) || "",
                        plan_id: select.dataset.cashAnalyticPlanId,
                    };
                })
                .filter(Boolean);
            if (!selectedAccounts.length || percentage <= 0) {
                continue;
            }
            const analyticAccountKey = selectedAccounts
                .map((account) => account.id)
                .join(",");
            const label = selectedAccounts
                .map((account) => account.label)
                .filter(Boolean)
                .join(" / ");
            distribution[analyticAccountKey] = {
                percentage,
                label,
                accounts: selectedAccounts,
            };
            total += percentage;
            summaries.push(`${label || analyticAccountKey} (${percentage}%)`);
        }

        if (!Object.keys(distribution).length) {
            setDistributionError(modalElement, "Select at least one analytic account.");
            return;
        }
        if (Math.abs(total - 100) > 0.0001) {
            setDistributionError(
                modalElement,
                "The analytic distribution must total 100%."
            );
            return;
        }

        const distributionInput = lineElement.querySelector(
            "[data-cash-line-distribution]"
        );
        const distributionDisplayInput = lineElement.querySelector(
            "[data-cash-line-distribution-display]"
        );
        const summaryElement = lineElement.querySelector(
            "[data-cash-distribution-summary]"
        );
        const summary = summaries.join(", ");
        distributionInput.value = JSON.stringify(distribution);
        distributionDisplayInput.value = summary;
        summaryElement.textContent = summary;
        lineElement.dataset.cashLineDirty = "1";
        hideModal(modalElement);
    }

    function initializeDistributionModal(rootElement) {
        const modalElement = getDistributionModal(rootElement);
        if (!modalElement || modalElement.dataset.cashDistributionReady) {
            return;
        }
        modalElement.dataset.cashDistributionReady = "1";

        modalElement
            .querySelector("[data-cash-distribution-add]")
            .addEventListener("click", () => addDistributionRow(modalElement, [], 100));
        modalElement
            .querySelector("[data-cash-distribution-save]")
            .addEventListener("click", () => saveDistributionModal(modalElement));
        modalElement
            .querySelectorAll("[data-cash-distribution-cancel]")
            .forEach((button) =>
                button.addEventListener("click", () => hideModal(modalElement))
            );
        modalElement.addEventListener("input", (event) => {
            if (event.target.closest("[data-cash-distribution-percentage]")) {
                updateDistributionTotal(modalElement);
            }
        });
        modalElement.addEventListener("click", (event) => {
            const removeButton = event.target.closest(
                "[data-cash-distribution-remove]"
            );
            if (!removeButton) {
                return;
            }
            removeButton.closest("[data-cash-distribution-row]").remove();
            updateDistributionTotal(modalElement);
        });
    }

    function initializeCashLines(rootElement) {
        if (rootElement.dataset.cashLinesReady) {
            return;
        }
        rootElement.dataset.cashLinesReady = "1";

        const lineList = rootElement.querySelector("[data-cash-line-list]");
        const lineTemplate = rootElement.querySelector("[data-cash-line-template]");
        const addButton = rootElement.querySelector("[data-cash-line-add]");
        if (!lineList || !lineTemplate || !addButton) {
            return;
        }

        addButton.addEventListener("click", () => {
            const lineElement = lineTemplate.content.firstElementChild.cloneNode(true);
            lineList.appendChild(lineElement);
            lineElement
                .querySelectorAll("[data-cash-analytic-search]")
                .forEach(initializeAnalyticSearch);
            updateLineRemoveButtons(rootElement);
        });

        lineList.addEventListener("click", (event) => {
            const distributionButton = event.target.closest(
                "[data-cash-distribution-open]"
            );
            if (distributionButton) {
                openDistributionModal(
                    rootElement,
                    distributionButton.closest("[data-cash-line]")
                );
                return;
            }
            const removeButton = event.target.closest("[data-cash-line-remove]");
            if (!removeButton) {
                return;
            }
            const lineElements = lineList.querySelectorAll("[data-cash-line]");
            if (lineElements.length <= 1) {
                return;
            }
            removeButton.closest("[data-cash-line]").remove();
            updateLineRemoveButtons(rootElement);
        });

        initializeDistributionModal(rootElement);
        updateLineRemoveButtons(rootElement);
    }

    function getAnalyticCreateModal() {
        return document.querySelector("[data-cash-analytic-create-modal]");
    }

    function setAnalyticCreateError(modalElement, message) {
        const errorElement = modalElement.querySelector(
            "[data-cash-analytic-create-error]"
        );
        if (!errorElement) {
            return;
        }
        errorElement.textContent = message || "";
        setVisible(errorElement, Boolean(message));
    }

    function openAnalyticCreateModal(searchRoot) {
        const modalElement = getAnalyticCreateModal();
        const nameInput = modalElement.querySelector(
            "[data-cash-analytic-create-name]"
        );
        if (!modalElement || !nameInput) {
            return;
        }
        modalElement.cashTargetRoot = searchRoot;
        nameInput.value = "";
        setAnalyticCreateError(modalElement, "");
        showModal(modalElement);
        nameInput.focus();
    }

    function saveAnalyticCreateModal(modalElement) {
        const searchRoot = modalElement.cashTargetRoot;
        const nameInput = modalElement.querySelector(
            "[data-cash-analytic-create-name]"
        );
        if (!searchRoot || !nameInput) {
            hideModal(modalElement);
            return;
        }

        const name = (nameInput.value || "").trim();
        if (!name) {
            setAnalyticCreateError(modalElement, "Please enter a name.");
            return;
        }

        const select = searchRoot.querySelector("[data-cash-analytic-select]");
        const displayInput = searchRoot.querySelector("[data-cash-analytic-display]");
        const form = searchRoot.closest("form");
        if (!select || !form) {
            hideModal(modalElement);
            return;
        }
        const planSelect = form.querySelector("[name='analytic_plan_id']");
        const companySelect = form.querySelector("[name='company_id']");
        const csrfInput = form.querySelector("[name='csrf_token']");
        const planId =
            select.dataset.cashAnalyticPlanId || (planSelect && planSelect.value);
        if (!planId) {
            setAnalyticCreateError(
                modalElement,
                "Please select an analytic plan first."
            );
            return;
        }

        const body = new FormData();
        body.append("name", name);
        body.append("plan_id", planId);
        if (companySelect && companySelect.value) {
            body.append("company_id", companySelect.value);
        }
        if (csrfInput) {
            body.append("csrf_token", csrfInput.value);
        }

        setAnalyticCreateError(modalElement, "");
        fetch("/cash/analytic_accounts/create", {
            method: "POST",
            body,
            credentials: "same-origin",
        })
            .then((response) =>
                response.json().then((payload) => ({ok: response.ok, payload}))
            )
            .then((result) => {
                if (!result.ok) {
                    setAnalyticCreateError(
                        modalElement,
                        result.payload.error || "Could not create the analytic account."
                    );
                    return;
                }
                const option = result.payload;
                if (select.tomselect) {
                    select.tomselect.addOption(option);
                    select.tomselect.setValue(option.id, true);
                } else {
                    select.value = option.id;
                }
                if (displayInput) {
                    displayInput.value = option.label;
                }
                hideModal(modalElement);
            })
            .catch(() =>
                setAnalyticCreateError(
                    modalElement,
                    "Could not create the analytic account."
                )
            );
    }

    function initializeAnalyticCreateModal() {
        const modalElement = getAnalyticCreateModal();
        if (!modalElement || modalElement.dataset.cashAnalyticCreateReady) {
            return;
        }
        modalElement.dataset.cashAnalyticCreateReady = "1";

        modalElement
            .querySelector("[data-cash-analytic-create-save]")
            .addEventListener("click", () => saveAnalyticCreateModal(modalElement));
        modalElement
            .querySelectorAll("[data-cash-analytic-create-cancel]")
            .forEach((button) =>
                button.addEventListener("click", () => hideModal(modalElement))
            );
    }

    function initializeAnalyticCreateButton(button) {
        if (button.dataset.cashAnalyticCreateReady) {
            return;
        }
        button.dataset.cashAnalyticCreateReady = "1";
        button.addEventListener("click", () =>
            openAnalyticCreateModal(button.closest("[data-cash-analytic-search]"))
        );
    }

    function initializeManualDistributionSync() {
        const select = document.querySelector("[name='manual_distribution_id']");
        if (!select || select.dataset.cashManualDistributionReady) {
            return;
        }
        select.dataset.cashManualDistributionReady = "1";
        select.addEventListener("change", refreshLineDefaults);
    }

    function initializeKassaOnlyToggle() {
        const toggle = document.querySelector("[data-cash-kassa-only-toggle]");
        if (!toggle || toggle.dataset.cashKassaOnlyReady) {
            return;
        }
        toggle.dataset.cashKassaOnlyReady = "1";

        const kassaOnlyFields = document.querySelector("[data-cash-kassa-only-fields]");
        const linesRoot = document.querySelector("[data-cash-lines]");

        function applyState() {
            const isKassaOnly = toggle.checked;
            setVisible(kassaOnlyFields, isKassaOnly);
            setVisible(linesRoot, !isKassaOnly);
            if (kassaOnlyFields) {
                kassaOnlyFields
                    .querySelectorAll("input, select, textarea, button")
                    .forEach((element) => {
                        element.disabled = !isKassaOnly;
                    });
            }
            if (linesRoot) {
                linesRoot
                    .querySelectorAll("input, select, textarea, button")
                    .forEach((element) => {
                        element.disabled = isKassaOnly;
                    });
            }
        }

        toggle.addEventListener("change", applyState);
        applyState();
    }

    function initializeAllAnalyticSearches() {
        document
            .querySelectorAll("[data-cash-analytic-search]")
            .forEach(initializeAnalyticSearch);
        document
            .querySelectorAll("[data-cash-partner-search]")
            .forEach(initializePartnerSearch);
        document.querySelectorAll("[data-cash-lines]").forEach(initializeCashLines);
        initializeAnalyticCreateModal();
        document
            .querySelectorAll("[data-cash-analytic-create]")
            .forEach(initializeAnalyticCreateButton);
        initializeManualDistributionSync();
        initializeKassaOnlyToggle();
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", initializeAllAnalyticSearches);
    } else {
        initializeAllAnalyticSearches();
    }
})();
