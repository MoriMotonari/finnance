import json
from http import HTTPStatus
import traceback

import datetime as dt
import sqlalchemy
from flask import Blueprint, abort, current_app, jsonify, redirect, request, url_for
from flask_login import current_user, login_required, login_user, logout_user
from jsonschema import Draft202012Validator, ValidationError, validate

from finnance import bcrypt, login_manager, db
from finnance.models import (Account, AccountTransfer, Agent, Category,
                             Currency, Flow, Record, Transaction, User)

api = Blueprint('api', __name__, url_prefix='/api',
                static_folder='static', static_url_path='/static/api')


class APIError(Exception):
    def __init__(self, status: HTTPStatus, msg=None):
        self.status = status
        self.msg = status.description if msg is None else msg


def check_input(schema):
    class Wrapper:
        def __init__(self, foo, schema):
            self.foo = foo
            self.__name__ = foo.__name__
            self.schema = schema
            self.validator = Draft202012Validator(schema=schema)

        def __call__(self, **kwargs):
            try:
                data = json.loads(request.data.decode())
                self.validator.validate(instance=data)
            except json.decoder.JSONDecodeError:
                raise APIError(HTTPStatus.BAD_REQUEST, "Non-JSON format")
            except ValidationError as err:
                raise APIError(HTTPStatus.BAD_REQUEST,
                               f"Invalid JSON schema: {err.message}")
            return self.foo(**data, **kwargs)

    return lambda foo: Wrapper(foo, schema)


@api.route("/exists", methods=["POST"])
@check_input({
    "type": "object",
    "properties": {
        "username": {"type": "string"}
    },
    "required": ["username"]
})
def exists_user(username: str):
    user = User.query.filter_by(username=username).first()
    exists = user is not None
    return jsonify({
        "exists": exists
    })


@api.route("/login", methods=["POST"])
@check_input({
    "type": "object",
    "properties": {
        "username": {"type": "string"},
        "password": {"type": "string"}
    },
    "required": ["username", "password"]
})
def login(username: str, password: str):
    user = User.query.filter_by(username=username).first()
    if not user:
        raise APIError(HTTPStatus.BAD_REQUEST, "Username doesn't exist")

    success = bcrypt.check_password_hash(user.password, password)
    if success:
        login_user(user)

    return jsonify({
        "auth": success,
    })


@api.route("/logout", methods=["POST"])
@login_required
def logout():
    return jsonify({
        "success": logout_user()
    })


@api.route("/session")
def session():
    if current_user.get_id() is None:
        return jsonify({
            "auth": False
        })
    else:
        return jsonify({
            "auth": True
        })

@api.route("/accounts/<int:account_id>")
@login_required
def account(account_id):
    # raise APIError(HTTPStatus.UNAUTHORIZED)
    acc = Account.query.filter_by(
        user_id=current_user.id, id=account_id).first()
    if acc is None:
        raise APIError(HTTPStatus.UNAUTHORIZED)
    return acc.api()

@api.route("accounts/<int:account_id>/changes")
@login_required
def changes(account_id):
    acc: Account = Account.query.filter_by(
        user_id=current_user.id, id=account_id).first()
    if acc is None:
        raise APIError(HTTPStatus.UNAUTHORIZED)
    
    kwargs = {"start": acc.date_created, "end": dt.datetime.now()}
    
    for key, val in request.args.to_dict().items():
        if key in kwargs and val != '':
            try:
                kwargs[key] = dt.datetime.fromisoformat(val)
            except ValueError:
                raise APIError(HTTPStatus.BAD_REQUEST)
    
    return acc.jsonify_changes(**kwargs)


@api.route("/me")
@login_required
def me():
    return jsonify(current_user.json(deep=True))

@api.route("/categories/<int:category_id>")
@login_required
def category(category_id):
    # raise APIError(HTTPStatus.UNAUTHORIZED)
    cat = Category.query.filter_by(
        user_id=current_user.id, id=category_id).first()
    if cat is None:
        raise APIError(HTTPStatus.UNAUTHORIZED)
    return jsonify(cat.json(deep=True))

@api.route("/agents")
@login_required
def agents():
    # raise APIError(HTTPStatus.UNAUTHORIZED)
    agents = Agent.query.filter_by(user_id=current_user.id).join(Transaction, isouter=True).join(
        Flow, sqlalchemy.and_(Agent.id == Flow.agent_id, 
        Transaction.id == Flow.trans_id), isouter=True).group_by(
            Agent.id).order_by(Agent.uses.desc(), Agent.desc).all()
    return jsonify([agent.json(deep=False) for agent in agents])

@api.route("/categories")
@login_required
def categories():
    categories = Category.query.filter_by(user_id=current_user.id).all()
    return jsonify([cat.json(deep=False) for cat in categories])

@api.errorhandler(APIError)
def handle_apierror(err: APIError):
    return jsonify({
        "msg": err.msg
    }), err.status.value


@api.errorhandler(Exception)
def handle_exception(err: Exception):
    """Return JSON instead of HTML for any other server error"""
    app = current_app
    app.logger.error(f"Unknown Exception: {str(err)}")
    app.logger.debug(''.join(traceback.format_exception(
        etype=type(err), value=err, tb=err.__traceback__)))
    return jsonify({
        "msg": f"{type(err).__name__}: {str(err)}"
    }), 500

@api.route("/transactions/add", methods=["POST"])
@login_required
@check_input({
    "type": "object",
    "properties": {
        "account_id": {"type": "number"},
        "amount": {"type": "number"},
        "date_issued": {"type": "string"},
        "is_expense": {"type": "boolean"},
        "agent": {"type": "string"},
        "comment": {"type": "string"},
        "flows": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "amount": {"type": "number"},
                    "agent": {"type": "string"},
                }
            }
        },
        "records": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "amount": {"type": "number"},
                    "category_id": {"type": "number"},
                }
            }
        },
    },
    "required": ["amount", "date_issued", "is_expense", "agent", "comment", "flows", "records"]
})
def add_trans(edit=None, **data):
    data['date_issued'] = dt.datetime.fromisoformat(data.pop('date_issued'))

    if data['account_id']:
        account = Account.query.get(data['account_id'])
        if account.user_id != current_user.id:
            return APIError(HTTPStatus.UNAUTHORIZED)
        # check saldo
        saldo = account.saldo
        # TODO: saldo at date_issued
        if edit is None:
            diff = -data['amount'] if data['is_expense'] else data['amount']
        else:
            tr = Transaction.query.get(edit)
            diff = tr.amount if tr.is_expense else -tr.amount
            diff += -data['amount'] if data['is_expense'] else data['amount']

        if saldo + diff < 0:
            return APIError(HTTPStatus.BAD_REQUEST,
                               "Transaction results in negative Account Saldo!")

        data['currency_id'] = account.currency_id

    def agent_createif(agent_desc):
        if agent_desc is None:
            return None
        agent = Agent.query.filter_by(desc=agent_desc).first()
        if not agent:
            agent = Agent(desc=agent_desc, user_id=current_user.id)
            db.session.add(agent)
            db.session.commit()
        return agent
    
    # AGENTs
    agent = agent_createif(data.pop('agent'))
    data['agent_id'] = agent.id
    # remote_agent = agent_createif(data.pop('remote_agent'))
    
    flows = data.pop('flows')

    for flow in flows:
        flow['agent_id'] = agent_createif(flow.pop('agent')).id
        flow['is_debt'] = not data['is_expense']
    
    records = data.pop('records')

    trans = Transaction(**data, user_id=current_user.id)
    db.session.add(trans)
    db.session.commit()
    for record in records:
        db.session.add(
            Record(**record, trans_id=trans.id)
        )
    for flow in flows:
        db.session.add(
            Flow(**flow, trans_id=trans.id)
        )
    db.session.commit()
        
    return jsonify({
        "success": True
    })

@login_manager.unauthorized_handler
def unauthorized():
    if request.blueprint == 'api':
        raise APIError(HTTPStatus.UNAUTHORIZED)
    return redirect(url_for('main.login'))
