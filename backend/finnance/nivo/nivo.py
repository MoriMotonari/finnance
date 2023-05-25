
from datetime import datetime
from http import HTTPStatus

from flask import Blueprint, jsonify, request
from flask_login import current_user, login_required
import sqlalchemy

from finnance.errors import APIError
from finnance.models import Agent, Transaction, Record, Category, Currency

nivo = Blueprint('nivo', __name__, url_prefix='/api/nivo')

@nivo.route("/sunburst")
@login_required
def sunburst():
    
    params = request.args.to_dict()
    if 'is_expense' not in params:
        raise APIError(HTTPStatus.BAD_REQUEST, 'is_expense must be in search parameters')
    if params['is_expense'] not in ['true', 'false']:
        raise APIError(HTTPStatus.BAD_REQUEST, "is_expense must be either 'true' or 'false'")
    is_expense = params['is_expense'] == 'true'
    if 'currency_id' not in params:
        raise APIError(HTTPStatus.BAD_REQUEST, 'currency_id must be in search parameters')
    try:
        c_id = int(params['currency_id'])
    except ValueError:
        raise APIError(HTTPStatus.BAD_REQUEST, 'currency_id must be integer')
    currency = Currency.query.filter_by(id=c_id, user_id=current_user.id).first()
    if currency is None:
        raise APIError(HTTPStatus.BAD_REQUEST, "invalid currency_id")
    min_date = None
    if 'min_date' in params:
        try:
            min_date = datetime.fromisoformat(params['min_date'])
        except ValueError:
            raise APIError(HTTPStatus.BAD_REQUEST, "min_date: invalid iso format")
    max_date = None
    if 'max_date' in params:
        try:
            max_date = datetime.fromisoformat(params['max_date'])
        except ValueError:
            raise APIError(HTTPStatus.BAD_REQUEST, "max_date: invalid iso format")

    def agents(cat, path):
        query = Agent.query.join(Transaction).join(Record).join(Category
            ).filter(Transaction.currency_id == currency.id).filter(Category.id == cat.id)
        if min_date is not None:
            query = query.filter(Transaction.date_issued >= min_date)
        if max_date is not None:
            query = query.filter(Transaction.date_issued < max_date)
        query = query.group_by(Agent).with_entities(
                sqlalchemy.func.sum(Record.amount).label('value'), 
                Agent.desc.label('name')
            )
        return [
            dict(
                color=cat.color,
                id=f'{path}.{row._asdict()["name"]}',
                **row._asdict()
            )
            for row in query
        ]

    def cat_obj(cat: Category, path=''):
        cat_children = Category.query.filter_by(parent_id=cat.id, user_id=current_user.id).order_by(Category.order).all()

        path = f'{path}.{cat.desc}'
        children = [
            cat_obj(ch, path=path) for ch in cat_children
        ] + agents(cat, path)
        
        return {
            'id': path,
            'name': cat.desc,
            'color': cat.color,
            'children': children,
        }

    def clean_recursion(obj):
        if 'children' not in obj:
            return obj
        children = [child['name'] for child in obj['children']]
        if children == [obj['name']]:
            # unnecessary level
            return obj['children'][0]
        else:
            for i, child in enumerate(obj['children']):
                obj['children'][i] = clean_recursion(child)
            return obj

    data = []
    for cat in Category.query.filter_by(parent_id=None, user_id=current_user.id, is_expense=is_expense
                                        ).order_by(Category.order):
        obj = cat_obj(cat)
        # obj = clean_recursion(obj)
        data.append(obj)
    return jsonify({'id': 'sunburst', 'color': '#ff0000', 'children': data})

@nivo.route("/bars")
@login_required
def bars():
    
    params = request.args.to_dict()
    if 'is_expense' not in params:
        raise APIError(HTTPStatus.BAD_REQUEST, 'is_expense must be in search parameters')
    if params['is_expense'] not in ['true', 'false']:
        raise APIError(HTTPStatus.BAD_REQUEST, "is_expense must be either 'true' or 'false'")
    is_expense = params['is_expense'] == 'true'
    if 'currency_id' not in params:
        raise APIError(HTTPStatus.BAD_REQUEST, 'currency_id must be in search parameters')
    try:
        c_id = int(params['currency_id'])
    except ValueError:
        raise APIError(HTTPStatus.BAD_REQUEST, 'currency_id must be integer')
    currency = Currency.query.filter_by(id=c_id, user_id=current_user.id).first()
    if currency is None:
        raise APIError(HTTPStatus.BAD_REQUEST, "invalid currency_id")
    min_date = None
    if 'min_date' in params:
        try:
            min_date = datetime.fromisoformat(params['min_date'])
        except ValueError:
            raise APIError(HTTPStatus.BAD_REQUEST, "min_date: invalid iso format")
    max_date = None
    if 'max_date' in params:
        try:
            max_date = datetime.fromisoformat(params['max_date'])
        except ValueError:
            raise APIError(HTTPStatus.BAD_REQUEST, "max_date: invalid iso format")
        
    def value(cat):
        query = Category.query.filter_by(id=cat.id).join(Record).join(
            Transaction).filter_by(currency_id=currency.id)
        if min_date is not None:
            query = query.filter(Transaction.date_issued >= min_date)
        if max_date is not None:
            query = query.filter(Transaction.date_issued < max_date)
        query = query.group_by(Category).with_entities(
                sqlalchemy.func.sum(Record.amount).label('value'), 
            )
        row = query.first()
        if row is None:
            return 0
        return row._asdict()['value']

    keys = []
    values = []

    def bar_obj(cat):
        bar = {
            'category': cat.desc,
            'color': cat.color,
        }

        def children(parent):
            v = value(parent)
            if v > 0:
                keys.append(parent.desc)
                values.append(v)
                bar[parent.desc] = value(parent)
                bar[f"{parent.desc}_color"] = parent.color
            cat_children = Category.query.filter_by(parent_id=parent.id, user_id=current_user.id).order_by(Category.order).all()
            for child in cat_children:
                children(child)
        children(cat)
        if len(bar.keys()) == 2:
            return None
        return bar

    data = []
    for cat in Category.query.filter_by(parent_id=None, user_id=current_user.id, is_expense=is_expense
                                        ).order_by(Category.order):
        bar = bar_obj(cat)
        if bar is not None:
            data.append(bar)

    # nivo expects all keys on all bars
    for key in keys:
        for bar in data:
            if key not in bar:
                bar[key] = 0
                bar[f"{key}_color"] =  Category.query.filter_by(
                    desc=key, is_expense=is_expense, user_id=current_user.id
                ).first().color

    return jsonify({'data': data, 'keys': keys, 'total': sum(values)})