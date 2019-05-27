# -*- coding: utf-8 -*-
# @Author Michael Pavlov
#
# version 1.00 2019-04-05
# первая версия

# version 1.10 2019-04-08
# + бродкаст сообщения
# + генерация служебной записки

# version 1.20 2019-04-08
# убрана логика выборочного реконнекта - что-то глючит, наблюдаем

# version 1.30 2019-04-08
# убрал лишнее в bot_poling

# version 1.31 2019-04-14
# поправил баг с проверкой new_user

# backlog:
# - если дата заполнения не заполнена - ставить текущую
# - если участник ДС не заполнен - брать из профиля юзера

# version 1.4 2019-05-13
# добвлена опция tor_requirement

# version 1.42 2019-05-14
# Поправил ссылку на хелп и сообщения
# нотификация о новых юзерах

# version 1.44 2019-05-17
# добавил ya music

import os
import telebot
from flask import Flask, request
import mysql.connector
import logging
import time
from logging.handlers import RotatingFileHandler
import validators
from urllib.parse import urlparse


class SaleMonBot:

    def __init__(self):

        self.logger = logging.getLogger("salemnon_bot")
        self.logger.setLevel(logging.DEBUG)
        fh = RotatingFileHandler("salemnon_bot.log", mode='a', encoding='utf-8', backupCount=5,
                                 maxBytes=16 * 1024 * 1024)
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        fh.setFormatter(formatter)
        self.logger.addHandler(fh)

        self.TG_BOT_TOKEN = os.environ['TOKEN']
        self.GLOBAL_RECONNECT_COUNT = os.environ['GLOBAL_RECONNECT_COUNT']
        self.reconnect_count = self.GLOBAL_RECONNECT_COUNT
        self.GLOBAL_RECONNECT_INTERVAL = 5
        self.RECONNECT_ERRORS = []
        self.ADMIN_ID = '211558'
        self.MAIN_HELP_LINK = "https://telegra.ph/usage-05-10"

        self.bot = telebot.TeleBot(self.TG_BOT_TOKEN)
        # telebot.apihelper.proxy = config.PROXY

        # привязываем хенделер сообщений к боту:
        self.bot.set_update_listener(self.handle_messages)
        handler_dic = self.bot._build_handler_dict(self.handle_callback_messages)
        # привязываем хенделр колбеков inline-клавиатуры к боту:
        self.bot.add_callback_query_handler(handler_dic)

        # Настройка Flask
        self.server = Flask(__name__)
        self.TELEBOT_URL = 'telebot_webhook/'
        self.BASE_URL = 'https://test-hw-bot.herokuapp.com/'

        self.server.add_url_rule('/' + self.TELEBOT_URL + self.TG_BOT_TOKEN, view_func=self.process_updates, methods=['POST'])
        self.server.add_url_rule("/", view_func=self.webhook)

        # настройа БД
        self.DB_DATABASE = "bots"
        self.DB_USER = os.environ['DB_USER']
        self.DB_PASSWORD = os.environ['DB_PASSWORD']
        self.DB_HOST = os.environ['DB_HOST']
        self.DB_PORT = os.environ['DB_PORT']

        if not self.mysql_reconnect():
            self.logger.critical("no database connection. Exit.")
            quit()

    def process_updates(self):
        self.bot.process_new_updates([telebot.types.Update.de_json(request.stream.read().decode("utf-8"))])
        return "!", 200

    def webhook(self):
        self.bot.remove_webhook()
        self.bot.set_webhook(url=self.BASE_URL + self.TELEBOT_URL + self.TG_BOT_TOKEN)
        return "!", 200

    def mysql_reconnect(self):
        while self.reconnect_count > 0:
            try:
                self.logger.info("Try reconnect...")
                self.reconnect_count = self.reconnect_count - 1

                self.connection_main = mysql.connector.connect(user=self.DB_USER, password=self.DB_PASSWORD,
                                                    host=self.DB_HOST, port=self.DB_PORT,
                                                    database=self.DB_DATABASE)
                self.connection_main.autocommit = True

                self.cursor_m = self.connection_main.cursor()
                self.logger.info("Reconnect successful")
                self.reconnect_count = self.GLOBAL_RECONNECT_COUNT
                return True
            except Exception as e:
                self.logger.warning("no database connection. try again" + str(e))
                time.sleep(self.GLOBAL_RECONNECT_INTERVAL)
        self.logger.critical("no database connection. Exit.")
        return False

    # method for inserts|updates|deletes
    def db_execute(self, query, params, comment = ""):
        try:
            for result_ in self.cursor_m.execute(query, params, multi=True):
                pass
        except mysql.connector.DatabaseError as err:
            self.logger.warning("Cant " + comment + ". Error: " + str(err))
            if err.errno not in self.RECONNECT_ERRORS: # не оттестировано, убираем пока проверку на ошибки
                if self.mysql_reconnect():
                    return self.db_execute(query, params, comment)
                else:
                    self.logger.critical("Cant " + comment)
                    return False
            else:
                self.logger.critical("Cant " + comment)
                return False
        except Exception as e:
            self.logger.critical("Cant " + comment + ". " + str(e))
        else:
            try:
                self.connection_main.commit()
                return True
            except Exception as e:
                self.logger.critical("Cant commit transaction " + comment + ". " + str(e))
        return False

    # method for selects
    def db_query(self, query, params, comment = ""):
        try:
            for result_ in self.cursor_m.execute(query, params, multi=True):
                pass
            try:
                result_set = self.cursor_m.fetchall()
                if result_set is None or len(result_set) <= 0:
                    result_set = []
                return result_set
            except:
                result_set = []
        except mysql.connector.DatabaseError as err:
            self.logger.warning("Cant " + comment + ". Error: " + str(err))
            if err.errno not in self.RECONNECT_ERRORS: # не оттестировано, убираем пока проверку на ошибки
                if self.mysql_reconnect():
                    return self.db_query(query, params, comment)
                else:
                    self.logger.critical("Cant " + comment)
                    return []
            else:
                self.logger.critical("Cant " + comment)
                return []
        except Exception as e:
            self.logger.critical("Cant "  + comment + ". " + str(e))
        return []

    def start_polling(self):
        while True:
            try:
                self.logger.info("Starting polling thread...")
                self.bot.polling()
            except Exception as e:
                self.logger.critical("Cant start Bot polling. " + str(e))
                time.sleep(2)

    def run(self):
        while True:
            try:
                self.webhook()
                self.server.run(host="0.0.0.0", port=int(os.environ.get('PORT', 5000)))
                self.logger.info("Server run")
                self.bot.send_message(self.ADMIN_ID, "Server run!")
            except Exception as e:
                self.logger.critical("Cant start Bot. RECONNECT" + str(e))
                time.sleep(2)

    def command_start(self, message):
        self.logger.info("Receive Start command from chat ID:" + str(message.chat.id))
        if message.from_user.username is not None:
            user_name = message.from_user.username
        else:
            user_name = message.from_user.first_name

        commands = ["/help", "/show", "/add"]
        if self.new_user(message.chat.id, user_name):
            self.bot.send_message(message.chat.id, "Your are in. tap /help", reply_markup=self.markup_keyboard(commands))
            self.bot.send_message(self.ADMIN_ID, "New user: " + str(user_name))
        else:
            self.bot.send_message(message.chat.id, "Welcome back " + str(message.from_user.username) + ". Tap /help", reply_markup=self.markup_keyboard(commands))

    def command_help(self, message):
        try:
            self.logger.info("Receive Help command from chat ID:" + str(message.chat.id))
            self.bot.send_message(message.chat.id, "Help:\n"
                              "/help - show this message\n"
                              "/add - add url\n"
                              "/show - show urls\n"
                              # "/ - edit your profile(TBD)\n"
                              #"/qq - get incomming questions(TBD)\n"
                              #"/... - ...\n"
                              "readme - " + self.MAIN_HELP_LINK + "\n"
                              "support - @m_m_pa\n"
                              "\n",disable_web_page_preview=True)
        except Exception as e:
            self.logger.critical("Cant execute Help command. " + str(e))
        return

    def command_usage(self, message):
        try:
            self.logger.info("Receive Usage command from chat ID:" + str(message.chat.id))
            self.bot.send_message(message.chat.id, "Usage:\n"
                          "*Фильтры*(для добавления к каждому URL).\n"
                          "Для *первого* использования рекомендуется *оставлять* \'\*\' или *пустым*.\n\n"  
                          "Добавляет раздел в подписку:\n"
                          "_+$ИмяРаздела_\n"
                          "Добавляет раздел и фильтрует по названию лота:\n"
                          "_+$ИмяРаздела:+слово,+оба слова,+(строгая фараза)_\n"
                          "Или также, но удаляем ненужные лоты по условиям в названии:\n"
                          "_+$ИмяРаздела:-стопслово,-(строгая стопфараза)_\n"
                          "Из раздела ничего не показывать:\n"
                          "_-$ИмяРаздела_\n"
                          "Подписаться на лоты со словами в названии:\n"
                          "_+слово_\n"
                          "Убрать лоты со словами в названии:\n"
                          "_-слово_\n\n"
                          "Одно условие - одна строка. Разделитель строк - перевод строки(shift-enter):\n"
                          "Список подписок вводится только целиком, полностью затирает старый список\n"    
                          "Количество строк - любое\n\n"   
                          "*Пример набора*: ищет в разделе Коллекционное лоты с словами эвм или куба, но исключает из выдачи марки и открытки, убирает раздел Бытовая техника, но включает все разделы Техника, включает все лоты с эвм и игра электроника, кроме лотов из явно запрещенных разделов.\n"
                          "_+$коллекционное:+эвм,+куба_\n"
                          "_-$бытовая техника_\n"
                          "_+$техника_\n"
                          "_-$марки_\n"
                          "_-$открытки_\n"
                          "_+эвм_\n"
                          "_+игра электроника_\n", parse_mode='Markdown')
        except Exception as e:
            self.logger.critical("Cant execute Usage command. " + str(e))
        return

    def command_add(self, message):
        self.logger.info("Receive Add command from chat ID:" + str(message.chat.id))
        # проверяем доступное количество URL

        urls_count = self.db_query("select count(*) from salemon_engine_urls where user_id = %s",(message.chat.id,), "Count urls")[0][0]
        max_urls_for_user = self.db_query("select max_urls from salemon_bot_users where user_id = %s",(message.chat.id,), "Get User Max Urls")[0][0]
        if urls_count >= max_urls_for_user:
            self.bot.send_message(message.chat.id, "Url limit exceeded.\nDelete other URLs or /upgrade account")
            return

        # если есть еще место - добавялем
        if self.db_execute("update salemon_bot_users set state = %s where user_id = %s", ("wait_url", message.chat.id), "Update State"):
            self.bot.send_message(message.chat.id, "Please paste url\nExample: http://www.domain.com/search?q=test")
        else:
            self.bot.send_message(message.chat.id, "ops...")
        return

    def command_show(self, message):
        self.logger.info("Receive Show command from chat ID:" + str(message.chat.id))
        urls = self.db_query("select url,subscription,url_id from salemon_engine_urls where user_id = %s", (message.chat.id,), "Get all urls")
        if len(urls) < 1:
            self.bot.send_message(message.chat.id,"No URLs yet.\nTap /add to add URL")
            return

        self.bot.send_message(message.chat.id, "Your URLs and filters:")
        keys = ["modify","delete"]
        for url in urls:
            url_message = self.bot.send_message(message.chat.id, url[0] + "\n" + url[1].replace("|","\n"), reply_markup=self.inline_keyboard(keys),disable_web_page_preview=True)
            try:
                self.db_execute("insert into salemon_bot_inline_urls (url_id,user_id,message_id) values (%s,%s,%s)", (url[2], message.chat.id, url_message.message_id), "Add inline url")
            except Exception as e:
                self.logger.critical("Cant insert urls into inline_table. " + str(e) + str(url_message))
                pass
        return

    def markup_keyboard(self, list):
        markupkeyboard = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True,row_width=7)
        markupkeyboard.add(*[telebot.types.KeyboardButton(name) for name in list])

        # remove keyboard
        # markup = telebot.types.ReplyKeyboardRemove(selective=False)
        # self.bot.send_message(message.chat.id, "",reply_markup=markup)
        return markupkeyboard

    def inline_keyboard(self, list):
        inlinekeyboard = telebot.types.InlineKeyboardMarkup(row_width=7)
        inlinekeyboard.add(*[telebot.types.InlineKeyboardButton(text=name, callback_data=name) for name in list])
        return inlinekeyboard

    def handle_messages(self, messages):
        for message in messages:
            if message.reply_to_message is not None:
                # TODO Process reply message
                return
            if message.text.startswith("/start"):
                self.command_start(message)
                self.db_execute("update salemon_bot_users set state = %s where user_id = %s", ("", message.chat.id),"Update State")
                return
            if message.text.startswith("/help"):
                self.command_help(message)
                return
            if message.text.startswith("/usage"):
                self.command_usage(message)
                self.db_execute("update salemon_bot_users set state = %s where user_id = %s", ("", message.chat.id),"Update State")
                return
            if message.text.startswith("/add"):
                self.command_add(message)
                return
            if message.text.startswith("/show"):
                self.command_show(message)
                return
            if message.text.startswith("/broadcast"):
                if int(message.chat.id) == int(self.ADMIN_ID):
                    self.broadcast(message.text.replace("/broadcast ",""))
                else:
                    self.bot.reply_to(message, "You are not admin")
                return
            if message.text.startswith("/"):
                self.bot.reply_to(message,"Unknown command. Tap /help")
                return

            # проверка на статусы:
            state =  self.db_query("select state from salemon_bot_users where user_id=%s", (message.chat.id,), "Get State")[0][0]

            if state == "wait_url":
                if self.add_url(message.chat.id, message.text):
                    self.db_execute("update salemon_bot_users set state = %s where user_id = %s",("", message.chat.id), "Update State")
                    self.bot.reply_to(message, "Done!")
                else:
                    self.bot.reply_to(message, "Not a valid url or unsupported site\nExample: http://www.domain.com/search?q=test")
                return

            if state.startswith("wait_subs_for_urlid"):
                url_id = state[state.find(":")+1:]
                if self.set_subscription(url_id, message.text):
                    self.db_execute("update salemon_bot_users set state = %s where user_id = %s",("", message.chat.id), "Update State")
                    self.bot.reply_to(message, "Done!")
                else:
                    self.bot.reply_to(message, "Not a valid format for this Domain\nHelp: " + self.MAIN_HELP_LINK)
                return

            # Если ничего не сработало
            # TODO проверть на урл и если да - вставлять

            # print(message)

            commands = ["/help","/show","/add"]
            self.bot.reply_to(message,text="Tap command", reply_markup=self.markup_keyboard(commands),parse_mode='Markdown')

    def handle_callback_messages(self,callback_message):
        # обязательный ответ в API
        self.bot.answer_callback_query(callback_message.id)

        # Разбор команд
        # команда удаления URL
        if callback_message.data == "delete":
            # достаем url_id:
            url_id = self.db_query("select url_id from bots.salemon_bot_inline_urls where user_id = %s and message_id = %s",(callback_message.message.chat.id,callback_message.message.message_id),"Get url_id")
            if len(url_id) < 1:
                # не нашли URL, отвечаем, что сорян
                keys = ["/show actual URLs"]
                self.bot.edit_message_text(chat_id=callback_message.message.chat.id,
                                           message_id=callback_message.message.message_id, text="Could not find URL.",
                                           reply_markup=self.inline_keyboard(keys), parse_mode='Markdown')
                return
            # Нашли url_id, удаляем url из БД
            if self.db_execute("delete from salemon_engine_urls where url_id = %s", (url_id[0][0],), "Delete URL"):
                # удалили успешно, правим сообщение:
                self.bot.edit_message_text(chat_id=callback_message.message.chat.id,
                                           message_id=callback_message.message.message_id, text="Deleted",
                                           parse_mode='Markdown')
                return
            else:
                self.logger.error("Cant delete URL:" + str(callback_message.chat.id))
                return

        # Команда показа списка URLs
        if callback_message.data.startswith("/show"):
            self.command_show(callback_message.message)
            return

        # Команда изменения правил b/w листов
        if callback_message.data == "modify":
            # достаем url_id:
            url_id = self.db_query(
                "select url_id from bots.salemon_bot_inline_urls where user_id = %s and message_id = %s",
                (callback_message.message.chat.id, callback_message.message.message_id), "Get url_id")
            if len(url_id) < 1:
                # не нашли URL, отвечаем, что сорян
                keys = ["/show actual URLs"]
                self.bot.edit_message_text(chat_id=callback_message.message.chat.id,
                                           message_id=callback_message.message.message_id, text="Could not find URL.",
                                           reply_markup=self.inline_keyboard(keys), parse_mode='Markdown')
                return
            else:
                # Нашли url_id, проверяем на наличие в основной таблице:
                if len(self.db_query("select url_id from bots.salemon_engine_urls where url_id = %s",(url_id[0][0],),"Get UrlId")) < 1:
                    # нет такого URL
                    keys = ["/show actual URLs"]
                    self.bot.edit_message_text(chat_id=callback_message.message.chat.id,
                                               message_id=callback_message.message.message_id,
                                               text="Could not find URL.",
                                               reply_markup=self.inline_keyboard(keys), parse_mode='Markdown')
                    return
                else:
                    # запоминаем и ставим статус с ожиданием
                    self.db_execute("update salemon_bot_users set state = %s where user_id = %s", ("wait_subs_for_urlid:"+str(url_id[0][0]), callback_message.message.chat.id),"Update State")
                    self.bot.send_message(callback_message.message.chat.id, "Please provide new filter list..")
            return



    #subscription = self.db_query("select subscription from salemon_engine_urls where url_id = %s",(url_id[0][0]),"Get Subscription")
    # print(callback_message.data)

        return

    def new_user(self, user_id, user_name):
        if len(self.db_query("select user_id from salemon_bot_users where user_id=%s", (user_id,), "Check User exist")) > 0:
            return False
        # add user:
        elif self.db_execute("insert into salemon_bot_users (name,user_id) values (%s,%s)", (user_name, user_id), "Add new User"):
            return True
        else:
            return False

    def add_url(self, user_id, url):
        # проверяем, что это корректный URL
        if not validators.url(url):
            return False

        priority = 0

        # проверяем, есть ли  нас парсер для нее
        parsed_uri = urlparse(url)
        domain = '{uri.netloc}'.format(uri=parsed_uri)
        if len(self.db_query("select parser_name from salemon_engine_parsers where domain = %s",(domain,),"Check Domain")) < 1:
            return False

        if len(url) > 1000:
            return False

        # определяем флаг tor
        if url.find("ebay.com") > 0:
            tor_requirement = 1
        else:
            tor_requirement = 0

        # дополнительная валидация ya music
        if url.find("music.yandex.ru") > 0:
            priority = 1
            if not url.endswith("albums/new"):
                return False

        if self.db_execute("insert into salemon_engine_urls (url,user_id,tor_requirement,priority) values (%s,%s,%s,%s)", (url, user_id, tor_requirement,priority), "Add url"):
            return True
        else:
            return False

    def set_subscription(self, url_id, subscription):
        if subscription.find("|") >= 0:
            return False
        if self.db_execute("update salemon_engine_urls set subscription = %s where url_id = %s", (subscription.replace("\n","|"),url_id),"Update subscription"):
            return True
        else:
            return False

    def broadcast(self, message):
        try:
            for item in self.db_query("select user_id from salemon_bot_users", (), "Get all Users"):
                self.bot.send_message(item[0],message)
        except Exception as e:
            self.logger.warning("Cant send broadcast message:" + str(e))

if __name__ == '__main__':

    dBot = SaleMonBot()
    dBot.run()
