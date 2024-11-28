from flask import Flask, request, jsonify, render_template, redirect, url_for, flash, Response, send_from_directory
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, login_user, logout_user, login_required, UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
import os
from werkzeug.utils import secure_filename
import csv
import io

# Ρυθμίσεις Flask
app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///finance.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.secret_key = 'your_secret_key'

# Ρυθμίσεις Βάσης Δεδομένων
db = SQLAlchemy(app)

# Ρύθμιση Login Manager
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# Μοντέλα
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(120), nullable=False)

class Transaction(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    type = db.Column(db.String(10))  # income ή expense
    amount = db.Column(db.Float, nullable=False)
    vat = db.Column(db.Float, nullable=False)
    description = db.Column(db.String(200))
    date = db.Column(db.Date, nullable=False)

class Invoice(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    file_name = db.Column(db.String(100), nullable=False)
    file_path = db.Column(db.String(200), nullable=False)
    upload_date = db.Column(db.Date, nullable=False)

# Φόρτωση χρήστη
@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# Διαδρομή για εγγραφή
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        existing_user = User.query.filter_by(username=username).first()
        if existing_user:
            flash("Το όνομα χρήστη είναι ήδη καταχωρημένο.", "error")
            return redirect(url_for('register'))

        hashed_password = generate_password_hash(password, method='pbkdf2:sha256')
        new_user = User(username=username, password=hashed_password)
        db.session.add(new_user)
        db.session.commit()

        flash("Η εγγραφή ολοκληρώθηκε επιτυχώς! Μπορείτε να συνδεθείτε.", "success")
        return redirect(url_for('login'))

    return render_template('register.html')

# Διαδρομή για Login και Logout
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(username=username).first()
        if user and check_password_hash(user.password, password):
            login_user(user)
            flash("Επιτυχής είσοδος!", "success")
            return redirect(url_for('dashboard'))
        else:
            flash("Λάθος όνομα χρήστη ή κωδικός!", "error")
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash("Αποσυνδεθήκατε!", "success")
    return redirect(url_for('login'))

# Διαδρομές Dashboard
@app.route('/dashboard')
@login_required
def dashboard():
    return render_template('dashboard.html')

@app.route('/add_transaction_page')
@login_required
def add_transaction_page():
    return render_template('add_transaction.html')

@app.route('/add_transaction', methods=['POST'])
@login_required
def add_transaction():
    try:
        # Λήψη δεδομένων από τη φόρμα
        type = request.form['type']
        amount = float(request.form['amount'])
        vat = float(request.form['vat'])
        description = request.form.get('description', '')
        date = datetime.strptime(request.form['date'], '%Y-%m-%d')

        # Δημιουργία νέας συναλλαγής
        new_transaction = Transaction(
            type=type,
            amount=amount,
            vat=vat,
            description=description,
            date=date
        )
        db.session.add(new_transaction)
        db.session.commit()

        flash("Η συναλλαγή καταχωρήθηκε επιτυχώς!", "success")
        return redirect(url_for('view_transactions'))
    except Exception as e:
        flash(f"Σφάλμα κατά την καταχώρηση: {str(e)}", "error")
        return redirect(url_for('add_transaction_page'))

@app.route('/upload_invoice_page')
@login_required
def upload_invoice_page():
    return render_template('upload_invoice.html')

@app.route('/upload_invoice', methods=['POST'])
@login_required
def upload_invoice():
    try:
        # Έλεγχος αν υπάρχει αρχείο στη φόρμα
        if 'file' not in request.files:
            flash("Δεν επιλέχθηκε αρχείο.", "error")
            return redirect(url_for('upload_invoice_page'))

        file = request.files['file']
        if file.filename == '':
            flash("Το αρχείο δεν έχει όνομα.", "error")
            return redirect(url_for('upload_invoice_page'))

        # Αποθήκευση αρχείου στον φάκελο uploads
        filename = secure_filename(file.filename)
        file_path = os.path.join('uploads', filename)
        file.save(file_path)

        # Καταχώρηση τιμολογίου στη βάση δεδομένων
        new_invoice = Invoice(
            file_name=filename,
            file_path=file_path,
            upload_date=datetime.now()
        )
        db.session.add(new_invoice)
        db.session.commit()

        flash("Το τιμολόγιο ανέβηκε επιτυχώς!", "success")
        return redirect(url_for('view_invoices'))
    except Exception as e:
        flash(f"Σφάλμα κατά το ανέβασμα: {str(e)}", "error")
        return redirect(url_for('upload_invoice_page'))


@app.route('/vat_summary')
@login_required
def vat_summary():
    transactions = Transaction.query.all()
    vat_in = sum(t.vat for t in transactions if t.type == 'income')
    vat_out = sum(t.vat for t in transactions if t.type == 'expense')
    vat_due = vat_in - vat_out
    return render_template('vat_summary.html', vat_in=vat_in, vat_out=vat_out, vat_due=vat_due)

# Συναλλαγές
@app.route('/view_transactions')
@login_required
def view_transactions():
    transactions = Transaction.query.all()
    return render_template('transactions.html', transactions=transactions)

@app.route('/edit_transaction/<int:id>', methods=['GET', 'POST'])
@login_required
def edit_transaction(id):
    transaction = Transaction.query.get_or_404(id)
    if request.method == 'POST':
        transaction.type = request.form['type']
        transaction.amount = float(request.form['amount'])
        transaction.vat = float(request.form['vat'])
        transaction.description = request.form.get('description', '')
        transaction.date = datetime.strptime(request.form['date'], '%Y-%m-%d')
        db.session.commit()
        flash("Η συναλλαγή ενημερώθηκε επιτυχώς!", "success")
        return redirect(url_for('view_transactions'))
    return render_template('edit_transaction.html', transaction=transaction)

@app.route('/delete_transaction/<int:id>', methods=['POST'])
@login_required
def delete_transaction(id):
    transaction = Transaction.query.get_or_404(id)
    db.session.delete(transaction)
    db.session.commit()
    flash("Η συναλλαγή διαγράφηκε επιτυχώς!", "success")
    return redirect(url_for('view_transactions'))

@app.route('/export_transactions', methods=['GET'])
@login_required
def export_transactions():
    transactions = Transaction.query.all()
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["ID", "Type", "Amount", "VAT", "Description", "Date"])
    for transaction in transactions:
        writer.writerow([
            transaction.id, transaction.type, transaction.amount,
            transaction.vat, transaction.description, transaction.date.strftime('%Y-%m-%d')
        ])
    output.seek(0)
    response = Response(output, mimetype="text/csv")
    response.headers["Content-Disposition"] = "attachment; filename=transactions.csv"
    return response

# Τιμολόγια
@app.route('/view_invoices')
@login_required
def view_invoices():
    invoices = Invoice.query.all()
    return render_template('invoices.html', invoices=invoices)

@app.route('/delete_invoice/<int:id>', methods=['POST'])
@login_required
def delete_invoice(id):
    invoice = Invoice.query.get_or_404(id)
    try:
        os.remove(invoice.file_path)
    except FileNotFoundError:
        pass
    db.session.delete(invoice)
    db.session.commit()
    flash("Το τιμολόγιο διαγράφηκε επιτυχώς!", "success")
    return redirect(url_for('view_invoices'))

@app.route('/uploads/<path:filename>')
@login_required
def uploads(filename):
    return send_from_directory('uploads', filename)

# Δημιουργία Βάσης Δεδομένων
if __name__ == '__main__':
    if not os.path.exists('uploads'):
        os.makedirs('uploads')
    with app.app_context():
        db.create_all()
    app.run(debug=True)
