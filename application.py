from flask import Flask, render_template, request, redirect, jsonify, url_for, flash
from functools import wraps
from sqlalchemy import create_engine, asc, desc
from sqlalchemy.orm import sessionmaker
from database import Base, Restaurant, MenuItem, User

from flask import session as login_session
import random
import string

from oauth2client.client import flow_from_clientsecrets
from oauth2client.client import FlowExchangeError
import httplib2
import json
from flask import make_response
import requests

app = Flask(__name__)
CLIENT_ID = json.loads(
    open('client_secrets.json', 'r').read())['web']['client_id']
APPLICATION_NAME = "Restaurant Menu Application"

engine = create_engine('sqlite:///restaurants.db')
Base.metadata.bind = engine

DBSession = sessionmaker(bind=engine)
session = DBSession()

# ezaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaay


def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'username' in login_session:
            return f(*args, **kwargs)
        else:
            flash("You are not allowed to access there")
            return redirect('/login')
    return decorated_function


@app.route('/')
@app.route('/home')
def callHome():
    allRes = session.query(Restaurant).all()
    lastItems = session.query(MenuItem).order_by(desc(MenuItem.datee)).limit(5)
    b = True
    if 'username' not in login_session:
        b = False
    return render_template("home.html", allRes=allRes, lastItems=lastItems, b=b)


@app.route('/gconnect', methods=['POST'])
def gconnect():
    # Validate state token
    if request.args.get('state') != login_session['state']:
        response = make_response(json.dumps('Invalid state parameter.'), 401)
        response.headers['Content-Type'] = 'application/json'
        return response
    # Obtain authorization code
    code = request.data

    try:
        # Upgrade the authorization code into a credentials object
        oauth_flow = flow_from_clientsecrets('client_secrets.json', scope='')
        oauth_flow.redirect_uri = 'postmessage'
        credentials = oauth_flow.step2_exchange(code)
    except FlowExchangeError:
        response = make_response(
            json.dumps('Failed to upgrade the authorization code.'), 401)
        response.headers['Content-Type'] = 'application/json'
        return response

    # Check that the access token is valid.
    access_token = credentials.access_token
    url = ('https://www.googleapis.com/oauth2/v1/tokeninfo?access_token=%s'
           % access_token)
    h = httplib2.Http()
    result = json.loads(h.request(url, 'GET')[1])
    # If there was an error in the access token info, abort.
    if result.get('error') is not None:
        response = make_response(json.dumps(result.get('error')), 500)
        response.headers['Content-Type'] = 'application/json'
        return response

    # Verify that the access token is used for the intended user.
    gplus_id = credentials.id_token['sub']
    if result['user_id'] != gplus_id:
        response = make_response(
            json.dumps("Token's user ID doesn't match given user ID."), 401)
        response.headers['Content-Type'] = 'application/json'
        return response

    # Verify that the access token is valid for this app.
    if result['issued_to'] != CLIENT_ID:
        response = make_response(
            json.dumps("Token's client ID does not match app's."), 401)
        print "Token's client ID does not match app's."
        response.headers['Content-Type'] = 'application/json'
        return response

    stored_credentials = login_session.get('credentials')
    stored_gplus_id = login_session.get('gplus_id')
    if stored_credentials is not None and gplus_id == stored_gplus_id:
        response = make_response(json.dumps('Current user is already connected.'),
                                 200)
        response.headers['Content-Type'] = 'application/json'
        return response

    # Store the access token in the session for later use.
    login_session['credentials'] = credentials.access_token
    login_session['gplus_id'] = gplus_id

    # Get user info
    userinfo_url = "https://www.googleapis.com/oauth2/v1/userinfo"
    params = {'access_token': credentials.access_token, 'alt': 'json'}
    answer = requests.get(userinfo_url, params=params)

    data = answer.json()

    login_session['username'] = data['name']
    login_session['email'] = data['email']

    # See if a user exists, if it doesn't make a new one
    user_id = getUserID(login_session['email'])
    if not user_id:
        user_id = createUser(login_session)
    login_session['user_id'] = user_id

    return redirect('/')


# User Helper Functions


def createUser(login_session):
    newUser = User(name=login_session['username'], email=login_session[
                   'email'])
    session.add(newUser)
    session.commit()
    user = session.query(User).filter_by(email=login_session['email']).one()
    return user.id


def getUserInfo(user_id):
    user = session.query(User).filter_by(id=user_id).one()
    return user


def getUserID(email):
    try:
        user = session.query(User).filter_by(email=email).one()
        return user.id
    except:
        return None


@app.route('/gdisconnect')
def gdisconnect():
        # Only disconnect a connected user.
    access_token = credentials
    if credentials is None:
        response = make_response(
            json.dumps('Current user not connected.'), 401)
        response.headers['Content-Type'] = 'application/json'
        return response
    access_token = credentials.access_token
    url = 'https://accounts.google.com/o/oauth2/revoke?token=%s' % access_token
    h = httplib2.Http()
    result = h.request(url, 'GET')[0]
    print('result : ')
    print(result)
    if result['status'] == '200':
        # Reset the user's sesson.
        del login_session['credentials']
        del login_session['gplus_id']
        del login_session['username']
        del login_session['email']

        response = make_response(json.dumps('Successfully disconnected.'), 200)
        response.headers['Content-Type'] = 'application/json'
        return redirect('/')
    else:
        # For whatever reason, the given token was invalid.
        response = make_response(
            json.dumps('Failed to revoke token for given user.', 400))
        response.headers['Content-Type'] = 'application/json'
        return response


@app.route('/category/<string:catName>/items')
def callCategory(catName):
    Res = session.query(Restaurant).filter_by(name=catName).one()
    allItems = session.query(MenuItem).filter_by(restaurant_id=Res.id).all()
    allCat = session.query(Restaurant).all()
    return render_template("category.html", Res=Res.name, allItems=allItems, allCat=allCat)


@app.route('/item/category/<string:catName>/<string:itemName>')
def callItem(catName, itemName):
    Item = session.query(MenuItem).filter_by(name=itemName).one()
    if 'username' not in login_session:
        return render_template("item.html", Item=Item, x=False)
    elif Item.user_id != login_session['user_id']:
        return render_template("item.html", Item=Item, b=True, x=False)
    else:
        return render_template("item.html", Item=Item, b=True, x=True)


@app.route('/catalog/add', methods=['POST', 'GET'])
@login_required
def callAdd():

    if request.method == 'POST':
        Res = session.query(Restaurant).filter_by(
        name = request.form['category']).one()
        newItem = MenuItem(name=request.form['title'],
                           description=request.form['description'],
                           restaurant_id=Res.id,
                           user_id=login_session['user_id']
                           )
        session.add(newItem)
        session.commit()
        return redirect('/')
    else:
        allCat = session.query(Restaurant).all()
        return render_template("add.html", cats=allCat, b=True)


@app.route('/catalog/<string:itemName>/edit', methods=['POST', 'GET'])
@login_required
def callEdit(itemName):
    item = session.query(MenuItem).filter_by(name=itemName).one()
    if item.user_id == login_session['user_id']:
        if request.method == 'POST':
            Res = session.query(Restaurant).filter_by(
                name=request.form['category']).one()
            item.name = request.form['title']
            item.description = request.form['description']
            item.restaurant_id = Res.id
            session.add(item)
            session.commit()
            return redirect('/')
        else:
            allCat = session.query(Restaurant).all()
            return render_template("edit.html", cats=allCat, item=item, b=True)
    else:
        return render_template('error.html')


@app.route('/catalog/<string:itemName>/delete', methods=['POST', 'GET'])
@login_required
def callDelete(itemName):
    # check if it's own
    item = session.query(MenuItem).filter_by(name=itemName).one()
    if item.user_id == login_session['user_id']:
        if request.method == 'POST':
            session.delete(item)
            session.commit()
            return redirect('/')
        else:
            return render_template("delete.html", b=True)
    else:
        return render_template('error.html')


@app.route('/login')
def callLogin():
    state = ''.join(random.choice(string.ascii_uppercase + string.digits)
                    for x in xrange(32))
    login_session['state'] = state
    return render_template("login.html", STATE=state)


@app.route('/catalog.json')
def calljson():
    allCat = session.query(Restaurant).all()
    result = []
    for cat in allCat:
        obj1 = cat.serialize
        allItem = session.query(MenuItem).filter_by(restaurant_id=cat.id).all()
        listt = []
        for item in allItem:
            listt.append(item.serialize)
        obj1['items'] = listt
        result.append(obj1)
    return jsonify(category=result)


if __name__ == '__main__':
    app.secret_key = 'super_secret_key'
    app.debug = True
    app.run(host='0.0.0.0', port=5000)
