from pymongo import MongoClient
from werkzeug.security import generate_password_hash
from user import User
from datetime import datetime
from bson.objectid import ObjectId
import pymongo

client = MongoClient('mongodb://localhost:27017')
users_collection = client['chatdb'].get_collection('users')
rooms_collection = client['chatdb'].get_collection('rooms')
room_members_collection = client['chatdb'].get_collection('room_members')
messages_collection = client['chatdb'].get_collection('messages')

def save(arg):
    password_hash = generate_password_hash(arg['password'])
    users_collection.insert_one({
        '_id': arg['username'],
        'email': arg['email'],
        'password': password_hash
    })

def get_user(username):
    user_data = users_collection.find_one({'_id': username})
    return User(user_data['_id'], user_data['email'], user_data['password']) if user_data else None

def save_room(room_name, created_by):
    rooms_collection.insert_one({
        'room_name': room_name,
        'created_by': created_by,
        'created_at': datetime.now()
    })
    room_id = rooms_collection.find({}, {'_id': 1}).sort('_id', pymongo.DESCENDING).limit(1)
    id = [str(i['_id']) for i in room_id]
    # print(id)
    add_room_member(id[0], room_name, created_by, created_by, True)
    return id[0]

def update_room(room_id, room_name):
    rooms_collection.update_one({'_id': ObjectId(room_id)}, {'$set': {
        'room_name': room_name
    }})
    room_members_collection.update_many({'_id.room_id': ObjectId(room_id)}, {'$set': {'room_name': room_name}})

def get_room(room_id):
    yield rooms_collection.find_one({'_id': ObjectId(room_id)})

def add_room_member(room_id, room_name, username, added_by, is_room_admin=False):
    room_members_collection.insert_one({
        '_id': {'room_id': ObjectId(room_id), 'username': username},
        'room_name': room_name,
        'added_by': added_by,
        'added_at': datetime.now(),
        'is_room_admin': is_room_admin
    })

def add_room_members(room_id, room_name, usernames, added_by):
    room_members_collection.insert_many([{
        '_id': {'room_id': ObjectId(room_id), 'username': username},
        'room_name': room_name,
        'added_by': added_by,
        'added_at': datetime.now(),
        'is_room_admin': False
    } for username in usernames])

def remove_room_members(room_id, usernames):
    room_members_collection.delete_many({'_id': {'$in': [{'room_id': ObjectId(room_id), 'username': username} for username in usernames]}})

def get_room_members(room_id):
    yield [i for i in room_members_collection.find({'_id.room_id': ObjectId(room_id)})]

def get_rooms_for_user(username):
    yield room_members_collection.find({'_id.username': username})

def is_room_member(room_id, username):
    yield room_members_collection.count_documents({'_id':{'room_id': ObjectId(room_id), 'username': username}})

def is_room_admin(room_id, username):
    yield room_members_collection.count_documents({'_id':{'room_id': ObjectId(room_id), 'username': username}, 'is_room_admin':True})


def save_message(room_id, text, sender):
    messages_collection.insert_one({
        'room_id': room_id,
        'text': text,
        'sender': sender,
        'created_at': datetime.now()
    })

MESSAGE_FETCH_LIMIT = 3
def get_messages(room_id, page=0):
    offset = page * MESSAGE_FETCH_LIMIT
    res = [i for i in messages_collection.find({'room_id': room_id}).sort('_id', pymongo.DESCENDING).limit(MESSAGE_FETCH_LIMIT).skip(offset)]
    for r in res:
        r['created_at'] = r['created_at'].strftime('%d %b, %H:%M')
    yield res[::-1]


# save({'username': 'jonribeiro23', 'email': 'jon@email.com', 'senha':'123456'})
