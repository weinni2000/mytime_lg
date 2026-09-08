Adds a "Search Invoice in Mail" button to the bank reconciliation widget's
transaction menu, next to "Upload Bills". It searches Gmail (via the `gog`
CLI) for an email matching the transaction's partner and amount, downloads
the first PDF attachment found, and attaches it exactly like a manual
"Upload Bills" would — creating and reconciling a vendor bill from it.
