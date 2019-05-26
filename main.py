import os
import telebot
from flask import Flask, request
import mysql.connector

# Connect to DB
DB_DATABASE = "bots"
DB_USER = os.environ['DB_USER']
DB_PASSWORD = os.environ['DB_PASSWORD']
DB_HOST = os.environ['DB_HOST']
DB_PORT = os.environ['DB_PORT']

API_TOKEN = os.environ['TOKEN']
bot = telebot.TeleBot(API_TOKEN)

server = Flask(__name__)
TELEBOT_URL = 'telebot_webhook/'
BASE_URL = 'https://test-hw-bot.herokuapp.com/'

# Handle '/start' and '/help'
@bot.message_handler(commands=['help', 'start'])
def send_welcome(message):
    bot.reply_to(message, "Hi! test version 1.2")

# Handle all other messages with content_type 'text' (content_types defaults to ['text'])
@bot.message_handler(func=lambda message: True)
def echo_message(message):
    bot.reply_to(message, message.text + "\n_test version 1.2_", parse_mode='Markdown')
    test_list = db_query("select name from properties",(), "Get")
    bot.reply_to(message,str(test_list))

# @server.route('/' + TELEBOT_URL + API_TOKEN, methods=['POST'])
def get_message():
    bot.process_new_updates([telebot.types.Update.de_json(request.stream.read().decode("utf-8"))])
    return "!", 200


# @server.route("/")
def webhook():
    bot.remove_webhook()
    bot.set_webhook(url=BASE_URL + TELEBOT_URL + API_TOKEN)
    return "!", 200

def db_query(query, params, comment = ""):
    try:
        for result_ in cursor_m.execute(query, params, multi=True):
            pass
        try:
            result_set = cursor_m.fetchall()
            bot.send_message(211558, "resulr = " + str(result_set))
            if result_set is None or len(result_set) <= 0:
                result_set = []
            return result_set
        except:
            result_set = []
    except mysql.connector.DatabaseError as err:
        print("Cant " + comment + ". Error: " + str(err))
    except Exception as e:
        print("Cant "  + comment + ". " + str(e))
    return []


connection_main = mysql.connector.connect(user=DB_USER, password=DB_PASSWORD,
                                                    host=DB_HOST, port=DB_PORT,
                                                    database=DB_DATABASE)
connection_main.autocommit = True
cursor_m = connection_main.cursor()

server.add_url_rule('/' + TELEBOT_URL + API_TOKEN, view_func=get_message,methods=['POST'])
server.add_url_rule("/", view_func=webhook)

webhook()
server.run(host="0.0.0.0", port=int(os.environ.get('PORT', 5000)))
