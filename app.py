from flask import Flask, render_template, request, jsonify
from flask_socketio import SocketIO, send, emit
import json, string, random, time
import hashlib, logging
import errors as e

from tinydb import TinyDB, Query
from tinydb.operations import add as aaa
from tinydb.operations import delete as ddd
from tinydb.operations import set as sss

app = Flask(__name__)

app.config['JSON_SORT_KEYS'] = False
app.config['JSONIFY_PRETTYPRINT_REGULAR'] = False

db = TinyDB('database/db.json', sort_keys=True, indent=4)
db_msg = TinyDB('database/db_msg.json', sort_keys=True, indent=4)

users = db.table('users')
messages = db_msg.table('messages')

@app.route('/')
def hello():
	return f'Api'


#  ┌─┐┌─┐┌─┐┌─┐┬ ┬┌┐┌┌┬┐
#  ├─┤│  │  │ ││ ││││ │ 
#  ┴ ┴└─┘└─┘└─┘└─┘┘└┘ ┴ 

@app.route('/method/account.register')
def account_register():
	name = request.args.get("name", "0")
	password = request.args.get("password", "0")
	password = hashlib.md5(password.encode()).hexdigest()

	ret = users.search(Query().name == name)
	if not ret: users.insert({'name': name, 'domain': name.lower(),
	'avatar': '', 'status': '', 'followers': '', 'following': '',
	'groups': '', 'password': password, 'token': generateToken()})
	else: ret = e.user_exists
	return jsonify(ret)

@app.route('/method/account.login')
def account_login():
	login = request.args.get("login".lower(), None)
	password = request.args.get("password", "0")
	password = hashlib.md5(password.encode()).hexdigest()
	token = request.args.get("token", None)
	if token: return jsonify(users.search(Query().token == token))
	else: return jsonify( users.search((Query().domain == login ) & (Query().password == password )) )

@app.route('/method/account.getFollowing')
def account_getFollowing():
	you = users.get(Query().token == request.args.get("token", "0"))
	if not you: return e.token_exp

	userr = request.args.get("user", None)
	if userr:
		user = users.get(Query().domain == userr)
		if not user: return e.user_not_found
		res = user['following']
	else: res = you['following']
	if not res: return {'error': 'No users following'}
	return jsonify(res)

@app.route('/method/account.getFollowers')
def account_getFollowers():
	you = users.get(Query().token == request.args.get("token", None))
	if not you: return e.token_exp

	userr = request.args.get("user", "0")
	if userr:
		user = users.get(Query().domain == userr)
		if not user: return e.user_not_found
		res = user['followers']
	else: res = you['followers']
	if not res: return {'error': 'No followers('}
	return jsonify(res)


#  ┬ ┬┌─┐┌─┐┬─┐┌─┐
#  │ │└─┐├┤ ├┬┘└─┐
#  └─┘└─┘└─┘┴└─└─┘

@app.route('/method/users.get/<string:domain>')
def users_get(domain):
	raw = users.get(Query().domain == domain)
	if not raw: ret = e.user_not_found
	else: ret = { "id": raw.doc_id, "domain": raw["domain"], "name": raw["name"] }
	return jsonify(ret)

@app.route('/method/users.follow')
def users_follow():
	you = users.get(Query().token == request.args.get("token", "0"))
	if not you: return e.token_exp
	userr = request.args.get("user", "0").lower()
	if not userr: return e.user_not_found
	user = users.get(Query().domain == userr)
	if not user: return e.user_not_found
	if userr == you['domain']: return {'error': 'Can\'t follow yourself' }
	if userr in you['following']: return {'error': 'Already following'}
	users.update(aaa('following', {user['domain']}), Query().domain == you['domain'])
	ret = {"request": "Following " + user["domain"] }
	return jsonify(ret)

@app.route('/method/users.unfollow')
def users_unfollow():
	you = users.get(Query().token == request.args.get("token", "0"))
	if not you: return e.token_exp
	userr = request.args.get("user", "0")
	if not userr: return e.user_not_found
	user = users.get(Query().domain == userr)
	if not user: return e.user_not_found
	if userr == you['domain']: return {'error': 'Can\'t unfollow yourself' }
	if userr not in you['following']: return {'error': 'Not following'}
	you['following'].remove(userr)
	users.update(you, Query().domain == you['domain'])
	ret = {"request": "Unfollowed " + user["domain"] }
	return jsonify(ret)


#  ┌┬┐┌─┐┌─┐┌─┐┌─┐┌─┐┌─┐┌─┐
#  │││├┤ └─┐└─┐├─┤│ ┬├┤ └─┐
#  ┴ ┴└─┘└─┘└─┘┴ ┴└─┘└─┘└─┘

@app.route('/method/messages.send')
def messages_send():
	to_ = request.args.get("to", "0").lower()
	message = request.args.get("message", "0")
	token = request.args.get("token", "0")

	you = users.get(Query().token == request.args.get("token", "0"))
	if to_ == you['domain']: return {'error': 'Can\'t send messages to yourself'} 
	if not you: return e.token_exp
	user = users.get(Query().domain == to_)
	if not user: return e.user_not_found

	raw = {'from': you["domain"], 'to': to_, 'message': message, 'time': time.time(), 'read': '0'}
	messages.insert(raw)

	return jsonify(raw)

@app.route('/method/messages.getConversations')
def getConversations():
	you = users.get(Query().token == request.args.get("token", "0"))
	lists = messages.search((Query()['to'] == you['domain']) | (Query()['from'] == you['domain']))
	if not lists: return {'error': 'No conversations'}
	return jsonify(lists)

@app.route('/method/messages.getByUser')
def messages_getByUser():
	to_ = request.args.get("user", "0").lower()
	you = users.get(Query().token == request.args.get("token", "0"))

	lists = messages.search((Query()['to'] == you['domain']) & (Query()['from'] == to_) | (Query()['to'] == to_) & (Query()['from'] == you['domain']))
	return jsonify(lists)

@app.route('/method/clear')
def clear():
	db.purge_table('users')
	return jsonify(db_msg.purge_table('messages'))


#  ┬ ┬┌─┐┌┐┌┌┬┐┬  ┌─┐┬─┐
#  ├─┤├─┤│││ │││  ├┤ ├┬┘
#  ┴ ┴┴ ┴┘└┘─┴┘┴─┘└─┘┴└─

@app.errorhandler(400)
def bad_request(error):
	return jsonify({'error': 'Bad Request'}), 400

@app.errorhandler(404)
def not_found(error):
	return jsonify({'error': 'JSON Error'}), 404

@app.errorhandler(500)
def handle_invalid_request(e):
	return jsonify({'error': '500'}), 500


def generateToken(stringLength=32):
	"""Generate a random string of fixed length """
	letters = string.ascii_letters + string.digits
	return ''.join(random.choice(letters) for i in range(stringLength))

if __name__ == '__main__':
	app.run(debug=True)