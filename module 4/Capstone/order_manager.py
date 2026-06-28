# order_manager.py
# Deliberately messy. Used as the input to the Module 4 capstone demo.

class OrderManager:
    def __init__(self, db, email_client, payment_gateway, logger):
        self.db = db
        self.email_client = email_client
        self.payment_gateway = payment_gateway
        self.logger = logger
        self.report_rows = []

    def process_order(self, order_data):
        # SMELL: Long method, God class, primitive obsession (raw dicts),
        # state mutation before failure, duplicated logic between branches.

        customer = order_data["customer"]
        items = order_data["items"]
        method = order_data["payment_method"]

        # 1) Pricing -- magic numbers everywhere, no value objects
        subtotal = 0
        for it in items:
            subtotal += it["price"] * it["qty"]
        if subtotal > 100:
            discount = subtotal * 0.10
        else:
            discount = 0
        tax = (subtotal - discount) * 0.07
        total = subtotal - discount + tax

        # 2) Inventory -- decrement BEFORE we know payment succeeds
        for it in items:
            row = self.db.query(
                "SELECT stock FROM inventory WHERE sku = ?", it["sku"]
            )
            if row["stock"] < it["qty"]:
                raise Exception("Out of stock: " + it["sku"])
            # BUG: state mutation before failure. If the payment step below
            # raises, inventory has already been written and is never rolled
            # back. The order row is persisted as PENDING too. Re-running the
            # same order double-decrements stock and orphans a PENDING row.
            self.db.execute(
                "UPDATE inventory SET stock = stock - ? WHERE sku = ?",
                it["qty"], it["sku"],
            )
        order_id = self.db.insert(
            "orders",
            {"customer": customer, "total": total, "status": "PENDING"},
        )

        # 3) Payment -- duplicated logic across the two branches
        if method == "credit_card":
            cc = order_data["card"]
            result = self.payment_gateway.charge_card(
                cc["number"], cc["exp"], cc["cvv"], total
            )
            if not result["ok"]:
                self.logger.log("Payment failed for " + customer)
                raise Exception("Card declined")
            txn_id = result["txn_id"]
            self.db.update("orders", order_id, {"status": "PAID", "txn": txn_id})
            self.email_client.send(
                customer, "Receipt", "You paid " + str(total)
            )
            self.report_rows.append([order_id, customer, total, "credit_card"])
        elif method == "paypal":
            pp = order_data["paypal"]
            result = self.payment_gateway.charge_paypal(
                pp["email"], pp["token"], total
            )
            if not result["ok"]:
                self.logger.log("Payment failed for " + customer)
                raise Exception("PayPal declined")
            txn_id = result["txn_id"]
            self.db.update("orders", order_id, {"status": "PAID", "txn": txn_id})
            self.email_client.send(
                customer, "Receipt", "You paid " + str(total)
            )
            self.report_rows.append([order_id, customer, total, "paypal"])
        else:
            raise Exception("Unknown payment method")

        return order_id

    def cancel_order(self, order_id):
        # SMELL: reaches into the DB directly, duplicates status strings,
        # no transaction, swallows errors.
        order = self.db.get("orders", order_id)
        if order is None:
            return False
        if order["status"] == "PAID":
            try:
                self.payment_gateway.refund(order["txn"], order["total"])
            except Exception:
                pass  # SMELL: silently ignore refund failures
        self.db.update("orders", order_id, {"status": "CANCELLED"})
        self.email_client.send(
            order["customer"], "Cancelled", "Your order was cancelled"
        )
        return True

    def generate_daily_report(self):
        # SMELL: reporting does NOT belong in OrderManager. Separate
        # responsibility that should live in its own service.
        total = 0
        lines = ["DAILY ORDER REPORT", "-" * 20]
        for r in self.report_rows:
            lines.append(
                str(r[0]) + " | " + r[1] + " | $" + str(r[2]) + " | " + r[3]
            )
            total += r[2]
        lines.append("-" * 20)
        lines.append("TOTAL: $" + str(total))
        report = "\n".join(lines)
        self.logger.log(
            "Report generated with " + str(len(self.report_rows)) + " rows"
        )
        return report

    def email_daily_report(self, admin_email):
        # SMELL: duplicates the email-sending pattern a third time.
        report = self.generate_daily_report()
        self.email_client.send(admin_email, "Daily Report", report)
        self.logger.log("Daily report emailed to " + admin_email)
        return True
