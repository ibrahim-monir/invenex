from datetime import date, datetime

from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


class Profile(db.Model):
    __tablename__ = "profile"

    id = db.Column(db.Integer, primary_key=True)
    display_name = db.Column(db.String(100))
    avatar_filename = db.Column(db.String(200))


class Item(db.Model):
    __tablename__ = "items"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    sku = db.Column(db.String(60))
    category = db.Column(db.String(80))
    unit = db.Column(db.String(20), nullable=False, default="pcs")
    quantity = db.Column(db.Integer, nullable=False, default=0)
    low_stock_threshold = db.Column(db.Integer, nullable=False, default=5)
    buying_price = db.Column(db.Float)
    selling_price = db.Column(db.Float)
    discount_price = db.Column(db.Float)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    logs = db.relationship(
        "StockLog", backref="item", lazy=True, order_by="StockLog.id.desc()",
        cascade="all, delete-orphan",
    )
    sales = db.relationship(
        "Sale", backref="item", lazy=True, order_by="Sale.id.desc()",
        cascade="all, delete-orphan",
    )

    @property
    def is_low_stock(self):
        return self.quantity <= self.low_stock_threshold


class StockLog(db.Model):
    __tablename__ = "stock_logs"

    id = db.Column(db.Integer, primary_key=True)
    item_id = db.Column(db.Integer, db.ForeignKey("items.id"), nullable=False)
    change_type = db.Column(db.String(3), nullable=False)  # "in" or "out"
    movement_type = db.Column(db.String(30))  # sale, restock, sponsor, damaged, personal_use, sample_gift, initial_stock, other
    quantity = db.Column(db.Integer, nullable=False)
    reason = db.Column(db.String(200))
    supplier = db.Column(db.String(120))
    po_number = db.Column(db.String(60))
    po_batch = db.Column(db.String(60))
    entry_date = db.Column(db.Date, default=date.today)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class Sale(db.Model):
    __tablename__ = "sales"

    id = db.Column(db.Integer, primary_key=True)
    item_id = db.Column(db.Integer, db.ForeignKey("items.id"), nullable=False)
    customer_name = db.Column(db.String(120))
    quantity = db.Column(db.Integer, nullable=False)
    amount = db.Column(db.Float, nullable=False)
    status = db.Column(db.String(10), nullable=False, default="due")  # "due" or "complete"
    sale_date = db.Column(db.Date, default=date.today)
    note = db.Column(db.String(300))
    income_id = db.Column(db.Integer, db.ForeignKey("income.id"))
    stock_log_id = db.Column(db.Integer, db.ForeignKey("stock_logs.id"))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    income = db.relationship("Income")


class Income(db.Model):
    __tablename__ = "income"

    id = db.Column(db.Integer, primary_key=True)
    purpose = db.Column(db.String(200), nullable=False)
    category = db.Column(db.String(80))
    amount = db.Column(db.Float, nullable=False)
    entry_date = db.Column(db.Date, default=date.today)
    note = db.Column(db.String(300))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class Expense(db.Model):
    __tablename__ = "expenses"

    id = db.Column(db.Integer, primary_key=True)
    purpose = db.Column(db.String(200), nullable=False)
    category = db.Column(db.String(80))
    amount = db.Column(db.Float, nullable=False)
    entry_date = db.Column(db.Date, default=date.today)
    note = db.Column(db.String(300))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class Supplier(db.Model):
    __tablename__ = "suppliers"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False, unique=True)
    contact = db.Column(db.String(120))
    notes = db.Column(db.String(300))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class Purchase(db.Model):
    __tablename__ = "purchases"

    id = db.Column(db.Integer, primary_key=True)
    supplier_id = db.Column(db.Integer, db.ForeignKey("suppliers.id"), nullable=False)
    po_number = db.Column(db.String(60))
    po_batch = db.Column(db.String(60))
    purchase_date = db.Column(db.Date, default=date.today)
    status = db.Column(db.String(10), nullable=False, default="due")  # "due" or "paid"
    total_amount = db.Column(db.Float, nullable=False, default=0)
    note = db.Column(db.String(300))
    expense_id = db.Column(db.Integer, db.ForeignKey("expenses.id"))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    supplier = db.relationship("Supplier")
    expense = db.relationship("Expense")
    lines = db.relationship(
        "PurchaseLine", backref="purchase", lazy=True, order_by="PurchaseLine.id",
        cascade="all, delete-orphan",
    )


class PurchaseLine(db.Model):
    __tablename__ = "purchase_lines"

    id = db.Column(db.Integer, primary_key=True)
    purchase_id = db.Column(db.Integer, db.ForeignKey("purchases.id"), nullable=False)
    item_id = db.Column(db.Integer, db.ForeignKey("items.id"), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    unit_price = db.Column(db.Float, nullable=False)
    stock_log_id = db.Column(db.Integer, db.ForeignKey("stock_logs.id"))

    item = db.relationship("Item")
