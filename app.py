from flask import Flask, url_for, request, redirect, jsonify, render_template
from flask_login import current_user, login_user, login_required, logout_user, LoginManager
from flask_socketio import SocketIO, join_room, leave_room
from flask_cors import CORS, cross_origin
import db
import pymongo
from datetime import datetime
from bson.json_util import dumps

app = Flask(__name__)
app.secret_key = "sfdjkafnk"
socketio = SocketIO(app)
login_manager = LoginManager()
login_manager.init_app(app)
cors = CORS(app)
app.config['CORS_HEADERS'] = 'Content-Type'


@app.route('/home')
@login_required
def home():
    return render_template('index.html')


@app.route('/', methods=['GET', 'POST'])
def login():
    rooms = []
    if current_user.is_authenticated:
        rooms = db.get_rooms_for_user(current_user.username)
        res = [i for i in rooms]
        res = [i for i in res[0]]
        return render_template('index.html', rooms=res)

    message = ''
    if request.method == 'POST':
        username = request.form['username']
        password_input = request.form['password']
        user = db.get_user(username)

        if user and user.check_password(password_input):
            login_user(user)
            return redirect('/')
        else:
            message = 'Failed to login!'
    return render_template('login.html', message=message)


@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if current_user.is_authenticated:
        return redirect('home')

    message = ''
    if request.method == 'POST':
        try:
            db.save(request.form)
            return redirect(url_for('/'))
        except pymongo.errors.DuplicateKeyError:
            message = 'User already exists.'

    return render_template('signup.html', message=message)

@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect('/')


@app.route('/create-room', methods=['GET', 'POST'])
@login_required
def create_room():
    message = ''
    if request.method == 'POST':
        room_name = request.form['room_name']
        usernames = [username.strip() for username in request.form['members'].split(',')]

        if len(room_name) and len(usernames):
            room_id = db.save_room(room_name, current_user.username)
            if current_user.username in usernames:
                usernames.remove(current_user.username)
            db.add_room_members(room_id, room_name, usernames, current_user.username)
            return redirect(url_for('view-room', room_id=room_id))
        else:
            message = 'Faild to create room.'

    return render_template('create-room.html', message=message)

@app.route('/room/<room_id>/',  methods=['GET'])
@login_required
def view_room(room_id):
    room = [i for i in db.get_room(room_id)]
    if room and db.is_room_member(room_id, current_user.username):
        room_members = [i for i in db.get_room_members(room_id)]
        messages = [i for i in db.get_messages(room_id)]
        return render_template('view-room.html', user=current_user.username, room=room[0], room_members=room_members[0], messages=messages[0])
    return 'Room not fould', 404


@app.route('/room/<room_id>/messages/',  methods=['GET'])
@login_required
def get_oldr_messages(room_id):
    room = [i for i in db.get_room(room_id)]
    if room and db.is_room_member(room_id, current_user.username):

        page = request.args.get('page', 0)
        messages = [i for i in db.get_messages(room_id, int(page))]
        return dumps(messages[0])
    return 'Room not fould', 404

@app.route('/room/<room_id>/edit',  methods=['GET', 'POST'])
@login_required
def edit_room(room_id):
    room = [i for i in db.get_room(room_id)]
    if room and db.is_room_admin(room_id, current_user.username):
        existing_room_members = [member for member in db.get_room_members(room_id)]
        existing_members = [str(member['_id']['username']) for member in existing_room_members[0]]

        if request.method == 'POST':
            room_name = request.form['room_name']
            db.update_room(room_id, room_name)

            new_members = [username.strip() for username in request.form['members'].split(',')]
            members_to_add = list(set(new_members) - set(existing_members))
            members_to_remove = list(set(existing_members) - set(new_members))

            if len(members_to_add):
                db.add_room_members(room_id, room_name, members_to_add, current_user.username)

            if len(members_to_remove):
                db.remove_room_members(room_id, members_to_remove)

            return redirect('/')

        room_members_str = ', '.join(existing_members)
        return render_template('edit-room.html', room=room[0], room_members_str=room_members_str)
    return 'Room not fould', 404


@socketio.on('send_message')
def handle_send_message_event(data):
    app.logger.info("{} has sent message to the room {}: {}".format(data['username'], data['room'], data['message']))
    data = {
        'username': data['username'],
        'room': data['room'],
        'message': data['message'],
        'created_at': datetime.now().strftime('%d %b, %H:%M')
    }

    db.save_message(data['room'], data['message'], data['username'])
    socketio.emit('receive_message', data, room=data['room'])


@socketio.on('join_room')
def handle_join_room_event(data):
    app.logger.info("{} has join the room {}".format(data['username'], data['room']))
    join_room(data['room'])
    socketio.emit('join_room_announcement', data)


@socketio.on('leave_room')
def handle_leave_room_event(data):
    app.logger.info("{} has join the room {}".format(data['username'], data['room']))
    leave_room(data['room'])
    socketio.emit('leave_room_announcement', data)

@login_manager.user_loader
def load_user(username):
    return db.get_user(username)

if __name__ == '__main__':
    socketio.run(app, debug=True, use_reloader=True)
