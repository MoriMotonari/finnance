from flask import Flask, render_template, Blueprint, request, redirect, url_for, jsonify, send_file
import sqlalchemy
from app import db
from app.main.models import AccountTransfer, Transaction, Account, Agent, Currency, Category
import datetime, io
import matplotlib.pyplot as plt
import seaborn as sns
import os

mod_main = Blueprint('main', __name__)

def trans_from_request(request, account):
    amount = float(request.form.get("amount"))
    is_expense = request.form.get("expinc") == 'expense'
    print(request.form.get("expinc"))

    date_issued = datetime.datetime.strptime(request.form.get("date_issued"), Transaction.input_format)
    if date_issued < account.date_created:
        return False, render_template("error.jinja", title="Creation Failed!", desc="Transaction can't have been executed before the creation of the account!", link=url_for('main.add_transaction'), link_text="Try again")
    if date_issued > datetime.datetime.now():
        return False, render_template("error.jinja", title="Creation Failed!", desc="Transaction can't have been executed after today!", link=url_for('main.add_transaction'), link_text="Try again")
    
    agent_desc = request.form.get("agent")
    agent = Agent.query.filter_by(desc=agent_desc).first()
    if not agent:
        agent = Agent(desc=agent_desc) 
        db.session.add(agent)
        db.session.commit()

    if is_expense:
        category_id = request.form.get("exp_category")
    else:
        category_id = request.form.get("inc_category")

    comment = request.form.get("comment")

    return True, dict(account_id=account.id, amount=amount, agent_id=agent.id, date_issued=date_issued, category_id=category_id, comment=comment, is_expense=is_expense)

@mod_main.route("/transfers/add/<int:src_id>-<int:dst_id>/", methods=["POST"])
def add_transfer(src_id, dst_id):
    src = Account.query.get(src_id)
    dst = Account.query.get(dst_id)
    src_amount = request.form.get("src_amount")
    dst_amount = request.form.get("dst_amount")
    date_issued = datetime.datetime.strptime(request.form.get("date_issued"), Transaction.input_format)
    if date_issued < src.date_created or date_issued < dst.date_created:
        return render_template("error.jinja", title="Creation Failed!", desc="Transfer can't have been executed before the creation of an account!", link=url_for('main.index'), link_text="Back")
    if date_issued > datetime.datetime.now():
        return render_template("error.jinja", title="Creation Failed!", desc="Transfer can't have been executed after today!", link=url_for('main.index'), link_text="Back")

    db.session.add(AccountTransfer(src_id=src_id, dst_id=dst_id, src_amount=src_amount, dst_amount=dst_amount, date_issued=date_issued))
    db.session.commit()
    return redirect(url_for('main.index'))

@mod_main.route("/accounts/<int:account_id>/transactions/add/", methods=["POST"])
def add_trans(account_id):
    account = Account.query.get(account_id)
    success, kwargs = trans_from_request(request, account)
    if not success:
        return kwargs
    db.session.add(Transaction(**kwargs))
    db.session.commit()
    return redirect(request.form.get("redirect"))

@mod_main.route("/transactions/edit/<int:transaction_id>", methods=["POST"])
def edit_trans(transaction_id):
    tr = Transaction.query.get(transaction_id)
    success, columns = trans_from_request(request, tr.account)
    if not success:
        return columns

    for key, val in columns.items():
        setattr(tr, key, val)
    db.session.commit()
    return redirect(request.form.get("redirect"))

@mod_main.route("/", methods=["GET"])
def index():
    accounts = Account.query.all()
    agents = Agent.query.order_by(Agent.desc).all()
    categories = Category.query.order_by(Category.desc).all()
    return render_template("main/home.j2", accounts=accounts, agents=agents, categories=categories)

@mod_main.route("/accounts/<int:account_id>", methods=["GET", "POST"])
def account(account_id):
    account = Account.query.get(account_id)
    agents = Agent.query.order_by(Agent.desc).all()
    categories = Category.query.order_by(Category.desc).all()
    saldo, saldo_children = account.saldo_children(num=5)
    return render_template("main/account.j2", agents=agents, account=account, categories=categories, last_5=saldo_children, saldo=saldo)

@mod_main.route("/add/account", methods=["GET", "POST"])
def add_account():
    currencies = Currency.query.all()
    if request.method == "GET":
        return render_template("main/add_acc.j2", currencies=currencies)
    else:
        desc = request.form.get("description")
        starting_saldo = float(request.form.get("starting_saldo"))
        date_created = datetime.datetime.strptime(request.form.get("date_created"), "%d.%m.%Y")
        if date_created > datetime.datetime.now():
            return render_template("error.jinja", title="Creation Failed!", desc="Account can't have been created after today!", link=url_for('main.add_account'), link_text="Try again")
        currency_id = int(request.form.get("currency"))
        account = Account(desc=desc, starting_saldo=starting_saldo, date_created=date_created, currency_id=currency_id)
        db.session.add(account) # pylint: disable=no-member
        try:
            db.session.commit() # pylint: disable=no-member
        except sqlalchemy.exc.IntegrityError:
            return render_template("error.jinja", title="Creation Failed!", desc="Account with same Description already exists!", link=url_for('main.add_account'), link_text="Try again")
        return redirect(url_for('main.add_account'))

@mod_main.route("/accounts/<int:account_id>/transactions")
def account_transactions(account_id):
    account = Account.query.get(account_id)
    agents = Agent.query.order_by(Agent.desc).all()
    categories = Category.query.order_by(Category.desc).all()
    
    saldo, saldo_children = account.saldo_children()
    
    return render_template("main/transactions.j2", account=account, saldo=saldo, transactions=saldo_children, agents=agents, categories=categories)

@mod_main.route("/accounts/<int:account_id>/plot")
def account_plot(account_id):
    account = Account.query.get(account_id)

    saldo, children = account.saldo_children(saldo_formatted=False)
    children = children[::-1]

    # Set seaborn & matplotlib
    sns.set("notebook", font_scale=2)
    f, ax = plt.subplots(figsize=(24, 6))
    plt.tight_layout()
    # creation, transactions and now
    x = [account.date_created]*2 + [child.date_issued for child in children] + [datetime.datetime.now()]
    y = [0, account.starting_saldo] + [child.saldo(formatted=False) for child in children] + [saldo]

    plt.plot(x, y, drawstyle='steps-post', linewidth=2.5)
    ax.set_xlim(left=x[0], right=[x[-1]])

    bytes_image = io.BytesIO()
    plt.savefig(bytes_image, format='png')
    bytes_image.seek(0)
    plt.close()

    return send_file(bytes_image,
                     attachment_filename='plot.png',
                     mimetype='image/png')

@mod_main.route("/accounts/<int:account_id>/analysis")
def account_analysis(account_id):
    pass

@mod_main.route("/transactions/<int:transaction_id>")
def transaction(transaction_id):
    transaction = Transaction.query.get(transaction_id)
    return jsonify(transaction.to_dict())

@mod_main.route("/api/transactions/<int:transaction_id>")
def api_transaction(transaction_id):
    transaction = Transaction.query.get(transaction_id)
    if not transaction:
        return jsonify({"error": "Invalid transaction_id!"}), 422

    return jsonify(transaction.to_dict())

@mod_main.route("/api/accounts/<int:account_id>")
def api_account(account_id):
    account = Account.query.get(account_id)
    if not account:
        return jsonify({"error": "Invalid account_id!"}), 422

    return jsonify(account.to_dict())

@mod_main.route("/api/agents/<int:agent_id>")
def api_agent(agent_id):
    agent = Agent.query.get(agent_id)
    if not agent:
        return jsonify({"error": "Invalid agent_id!"}), 422

    return jsonify(agent.to_dict())

# CODE BELOW IS FOR FORCE RELOADING CSS
@mod_main.context_processor
def override_url_for():
    return dict(url_for=dated_url_for)

def dated_url_for(endpoint, **values):
    import os
    if endpoint == 'static':
        filename = values.get('filename', None)
        if filename:
            file_path = os.path.join(mod_main.root_path, '..',
                                 endpoint, filename)
            values['q'] = int(os.stat(file_path).st_mtime)
    return url_for(endpoint, **values)