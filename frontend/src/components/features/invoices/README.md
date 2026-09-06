# Invoice workflow

Invoice lifecycle and payment status are separate. Finalize uses the existing invoice API hooks; Add Payment requires Accepted, finalized/accepted timestamps, and a positive outstanding balance. Legacy is receipt display only.

Pending payments are saved to sessionStorage under user ID and invoice ID before submission. After an uncertain response, the payload stays locked and retries reuse its Idempotency-Key, including after a reload or remount in the same tab. Successful responses, validation failures, and explicit balance/acceptance rejections clear that operation; idempotency conflicts do not. Closing the dialog preserves it. Storage failures stop submission; clearing browser storage or starting a new tab cannot restore an uncertain operation, so check existing receipts first.

Public invoice links use /public/invoice#<64hex>. The raw fragment is submitted in the POST body with cookies omitted. Public acceptance refetches the authoritative invoice; it does not initiate a payment. Public errors never clear an existing CRM session.

Amounts accept decimal strings or numbers. InvoiceItemsTable shows server-calculated totals, currency, and tax/discount rates in both views. InvoiceSummary renders the supplied billing snapshot without prescribing its nested structure.

Sending queues delivery. The detail page refreshes while delivery_status is Pending and displays the server's status. Subscription changes remain administrator managed; legacy payment-result routes offer guidance only.
