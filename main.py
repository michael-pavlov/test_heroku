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

# version 1.45 2019-05-27
# портировано на webhook, heroku

# version 1.46 2019-05-27
# add stop

# version 1.48 2019-06-01
# add tele2 hack support
# bugfix

# version 1.50 2019-06-01
# update Usage
# version 1.51 2019-06-01
# version 1.52 2019-06-16
# add www.olx.ua
# fix domain check process
# version 1.53 2019-06-16
# fix broadcasts
# version 1.54 2019-07-07
# donate, refactor markup_commands, fix m.avito
# version 1.56 2019-08-03
# add titles in /show
# blocked flag
# version 1.57

import os
import telebot
from flask import Flask, request
import mysql.connector
import logging
import time
import validators
from urllib.parse import urlparse
import sys
from datetime import datetime, timedelta

VERSION = "1.57d"


class SaleMonBot:

    def __init__(self, env = "heroku"):

        self.logger = logging.getLogger("SalemonBot")
        self.logger.setLevel(logging.DEBUG)
        handler = logging.StreamHandler(sys.stdout)
        handler.setLevel(logging.DEBUG)
        formatter = logging.Formatter('%(name)s: %(levelname)s: %(message)s')
        handler.setFormatter(formatter)
        self.logger.addHandler(handler)

        if env == 'heroku':
            self.TG_BOT_TOKEN = os.environ['TOKEN']
            self.GLOBAL_RECONNECT_COUNT = int(os.environ['GLOBAL_RECONNECT_COUNT'])
            # настройка БД
            self.DB_DATABASE = "bots"
            self.DB_USER = os.environ['DB_USER']
            self.DB_PASSWORD = os.environ['DB_PASSWORD']
            self.DB_HOST = os.environ['DB_HOST']
            self.DB_PORT = os.environ['DB_PORT']
        else:
            self.TG_BOT_TOKEN = config.TG_BOT_TOKEN
            self.GLOBAL_RECONNECT_COUNT = int(config.GLOBAL_RECONNECT_COUNT)
            self.DB_DATABASE = "bots"
            self.DB_USER = config.DB_USER
            self.DB_PASSWORD = config.DB_PASSWORD
            self.DB_HOST = config.DB_HOST
            self.DB_PORT = config.DB_PORT

        self.reconnect_count = self.GLOBAL_RECONNECT_COUNT
        self.GLOBAL_RECONNECT_INTERVAL = 5
        self.RECONNECT_ERRORS = []
        self.ADMIN_ID = '211558'
        self.MAIN_HELP_LINK = "https://telegra.ph/usage-05-10"
        self.TRIAL_DAYS = 3

        self.new_user_welcome_message = "Привет. Я умею уведомлять тебя о новых объявлениях.\n" + \
                                        "На выбранной площадке сформируй поисковый запрос. Обязательно поставь настройки отображения \"сначала новые\"\n" + \
                                        "Потом в боте нажми /add и отправь содержимое адресной строки\n" + \
                                        "\n" + \
                                        "Вот тут подробнее и со скриншотами: " + self.MAIN_HELP_LINK + "\n\n" + \
                                        "Мы регулярно отслеживаем изменения на площадках, чтобы успевать все парсить, поэтому бот не бесплатный\n" + \
                                        "У тебя будет 3 дня и 3 ссылки для оценки работы бота, потом от 2$ в месяц\n" + \
                                        "Если тебе нужно получать обновления быстро, то можно оформить выделенный сервис с задержкой в несколько минут\n\n" + \
                                        "Подробнее про тарифы - /upgrade\n" + \
                                        "По любым вопросам пиши @m_m_pa"

        self.bot = telebot.TeleBot(self.TG_BOT_TOKEN)
        # telebot.apihelper.proxy = config.PROXY

        self.markup_commands = ["/show", "/add", "/help", "/upgrade"]

        # привязываем хенделер сообщений к боту:
        self.bot.set_update_listener(self.handle_messages)
        handler_dic = self.bot._build_handler_dict(self.handle_callback_messages)
        # привязываем хенделр колбеков inline-клавиатуры к боту:
        self.bot.add_callback_query_handler(handler_dic)

        # Настройка Flask
        self.server = Flask(__name__)
        self.TELEBOT_URL = 'telebot_webhook/'
        self.BASE_URL = 'https://test-hw-bot.herokuapp.com/'

        self.server.add_url_rule('/' + self.TELEBOT_URL + self.TG_BOT_TOKEN, view_func=self.process_updates,
                                 methods=['POST'])
        self.server.add_url_rule("/", view_func=self.webhook)

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
                self.connection_main.reconnect(attempts=3,delay=2)

                self.cursor_m = self.connection_main.cursor(buffered=True)
                self.logger.info("Reconnect successful " + str(self.connection_main.is_connected()))
                self.reconnect_count = self.GLOBAL_RECONNECT_COUNT
                return True
            except Exception as e:
                self.logger.warning("no database connection. try again" + str(e))
                time.sleep(self.GLOBAL_RECONNECT_INTERVAL)
        self.logger.critical("no database connection. Exit.")
        return False

    # method for inserts|updates|deletes
    def db_execute(self, query, params, comment=""):
        try:
            for result_ in self.cursor_m.execute(query, params, multi=True):
                pass
        except Exception as err:
            self.logger.warning("Cant " + comment + ". Error: " + str(err))
            if self.mysql_reconnect():
                return self.db_execute(query, params, comment)
            else:
                self.logger.critical("Cant " + comment)
                return False
        else:
            try:
                self.connection_main.commit()
                return True
            except Exception as e:
                self.logger.critical("Cant commit transaction " + comment + ". " + str(e))
        return False

    # method for selects
    def db_query(self, query, params, comment=""):
        try:
            self.logger.info("db_query()" + comment)
            for result_ in self.cursor_m.execute(query, params, multi=True):
                pass
            try:
                result_set = self.cursor_m.fetchall()
                self.logger.debug("db_query().result_set:" + str(result_set))
                if result_set is None or len(result_set) <= 0:
                    result_set = []
                return result_set
            except Exception as erro:
                self.logger.warning("Cant " + comment + ". Error0: " + str(erro))
                result_set = []
        except Exception as err:
            self.logger.warning("Cant " + comment + ". Error: " + str(err))
            if self.mysql_reconnect():
                return self.db_query(query, params, comment)
            else:
                self.logger.critical("Cant " + comment)
                return []
        # except Exception as e:
        #    self.logger.critical("Cant "  + comment + ". " + str(e))
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
                self.logger.info("Server run. Version: " + VERSION)
                self.webhook()
                self.server.run(host="0.0.0.0", port=int(os.environ.get('PORT', 5000)))
            except Exception as e:
                self.logger.critical("Cant start Bot. RECONNECT" + str(e))
                time.sleep(2)

    def command_start(self, message):
        self.logger.info("Receive Start command from chat ID:" + str(message.chat.id))
        if message.from_user.username is not None:
            user_name = message.from_user.username
        else:
            user_name = message.from_user.first_name

        if self.new_user(message.chat.id, user_name):
            self.bot.send_message(message.chat.id, self.new_user_welcome_message,
                                  reply_markup=self.markup_keyboard(self.markup_commands))
            self.bot.send_message(self.ADMIN_ID, "New user: " + str(user_name))
        else:
            self.bot.send_message(message.chat.id, "Welcome back " + str(message.from_user.username) + ". Tap /help",
                                  reply_markup=self.markup_keyboard(self.markup_commands))
            self.bot.send_message(message.chat.id, self.new_user_welcome_message,
                                  reply_markup=self.markup_keyboard(self.markup_commands))
            self.db_execute("update salemon_bot_users set blocked = '0', reason = '' where user_id = %s", (str(message.chat.id),), "Command Start() Clear flags")

    def command_help(self, message):
        try:
            self.logger.info("Receive Help command from chat ID:" + str(message.chat.id))
            self.bot.send_message(message.chat.id, "Help:\n"
                                                   "/usage - show usage(en)\n"
                                                   "/add - add url\n"
                                                   "/show - show urls\n"
                                                   "readme(ru) - " + self.MAIN_HELP_LINK + "\n"
                                                   "support - @m_m_pa\n\n"
                                                   "version - " + VERSION + "\n"
                                                   "\n",
                                  disable_web_page_preview=True, reply_markup=self.markup_keyboard(self.markup_commands))
        except Exception as e:
            self.logger.critical("Cant execute Help command. " + str(e))
        return

    def command_donate(self, message):
        try:
            self.db_execute("update salemon_bot_users set state = %s where user_id = %s", ("", message.chat.id),"Update State")
            self.logger.info("Receive Donate command from chat ID:" + str(message.chat.id))
            self.bot.send_message(message.chat.id, "*Donate project*:\n"
                                                   "PayPal: https://paypal.me/mrmichaelpavlov\n"
                                                   "VK pay: https://vk.me/moneysend/to/23QW\n"
                                                   "Mastercard: 5321 3046 4588 4500\n"
                                                   "ETH: 0x6dD6E739891D15A3dcEFF9587dECC780a3809246\n"
                                                   "BTC: 1FzUWXtViv1MtvyrgcPGSmwnusHAaUXxLM\n"
                                                   "\n",
                                  disable_web_page_preview=True, parse_mode='Markdown',reply_markup=self.markup_keyboard(self.markup_commands))
        except Exception as e:
            self.logger.critical("Cant execute Donate command. " + str(e))
        return

    def command_usage(self, message):
        try:
            self.logger.info("Receive Usage command from chat ID:" + str(message.chat.id))
            self.bot.send_message(message.chat.id, "*Usage*:\n"
                                                   "1. Go to one of supported sites, make search with your own filters and options\n"
                                                   "2. Sort mode must be *\"newest first\"* or the same\n"
                                                   "3. Copy URL from address line in brouser\n"
                                                   "4. Go to bot and tap /add command\n"
                                                   "5. Paste URL. Wait \"Done\" message\n"
                                                   "6. Thats it! New ads will come to this chat\n"
                                                   "\n"
                                                   "*Support sites*:\n"
                                                   "ebay.com\n"
                                                   "avito.ru\n"
                                                   "youla.ru \n"
                                                   "music.yandex.ru\n"
                                                   "sob.ru\n"
                                                   "kvartirant.ru\n"
                                                   "thelocals.ru\n"
                                                   "kvadroom.ru\n"
                                                   "www.olx.ua\n"
                                                   "www.olx.uz\n"
                                                   "www.shafa.ua\n"
                                                   "www.meshok.net\n"
                                                   "\n", parse_mode='Markdown', reply_markup=self.markup_keyboard(self.markup_commands))
        except Exception as e:
            self.logger.critical("Cant execute Usage command. " + str(e))
        return

    def command_stop(self, message):
        try:
            self.logger.info("Receive Stop command from chat ID:" + str(message.chat.id))
            self.bot.send_message(self.ADMIN_ID, "Stop user: " + str(message.chat.id))
        except Exception as e:
            self.logger.critical("Cant execute Stop command. " + str(e))
        return

    def command_add(self, message):
        self.logger.info("Receive Add command from chat ID:" + str(message.chat.id))

        try:
            # проверяем доступное количество URL
            urls_count = \
            self.db_query("select count(*) from salemon_engine_urls where user_id = %s", (message.chat.id,), "Count urls")[
                0][0]
            max_urls_for_user = \
            self.db_query("select max_urls from salemon_bot_users where user_id = %s", (message.chat.id,),
                          "Get User Max Urls")[0][0]
            if urls_count >= max_urls_for_user:
                self.bot.send_message(message.chat.id, "Url limit exceeded.\nDelete other URLs or /upgrade account")
                return

            # если есть еще место - добавляем
            if self.db_execute("update salemon_bot_users set state = %s where user_id = %s", ("wait_url", message.chat.id),
                               "Update State"):
                self.bot.send_message(message.chat.id, "Please paste url\nExample: http://www.domain.com/search?q=test")
            else:
                self.bot.send_message(message.chat.id, "ops...")
        except Exception as e:
            self.logger.info("Cant execute Add command from chat ID:" + str(message.chat.id))
            try:
                self.bot.send_message(message.chat.id, "ops... please tap /start or contact support")
            except:
                pass
        return

    def command_show(self, message):
        try:
            self.logger.info("Receive Show command from chat ID:" + str(message.chat.id))
            urls = self.db_query("select url,subscription,url_id,title from salemon_engine_urls where user_id = %s",
                                 (message.chat.id,), "Get all urls")
            self.logger.debug("Urls: " + str(urls))
            if len(urls) < 1:
                self.bot.send_message(message.chat.id, "No URLs yet.\nTap /add to add URL",reply_markup=self.markup_keyboard(self.markup_commands))
                return

            self.bot.send_message(message.chat.id, "Your URLs and filters:")
            keys = ["modify", "delete"]
            for url in urls:
                url_message = self.bot.send_message(message.chat.id, url[3] + "\n" + url[0] + "\n" + url[1].replace("|", "\n"),
                                                    reply_markup=self.inline_keyboard(keys),
                                                    disable_web_page_preview=True)
                try:
                    self.db_execute("insert into salemon_bot_inline_urls (url_id,user_id,message_id) values (%s,%s,%s)",
                                    (url[2], message.chat.id, url_message.message_id), "Add inline url")
                except Exception as e:
                    self.logger.critical("Cant insert urls into inline_table. " + str(e) + str(url_message))
                    pass
        except Exception as err:
            self.logger.critical("Cant execute Show: " + str(err))
        return

    def command_upgrade(self, message):
        try:
            self.logger.info("Receive Upgrade command from chat ID:" + str(message.chat.id))
            self.bot.send_message(self.ADMIN_ID, "Receive Upgrade command from chat ID: " + str(message.chat.id))
            self.bot.send_message(message.chat.id, "Для покупки выберите и оплатите план на сервисе Patreon: https://www.patreon.com/pavlovsolutions\n"
                                                   "После оплаты напишите в бота сообщение вида \"patreon member <>\", указав свой member name\n"
                                                   "\n"
                                                   "Варианты подписки:\n"
                                                   "3 ссылки - 2$ в месяц\n"
                                                   "10 ссылок - 5$ в месяц \n"
                                                   "20 ссылок - 10$ в месяц\n"
                                                   "Выделенный сервис (10 ссылок, задержка 1 мин.) - свяжитесь @m_m_pa\n"
                                                   "Разработка под вас - свяжитесь @m_m_pa\n"
                                                   "\n"
                                                   "Select prefered plan and pay on Patreon: https://www.patreon.com/pavlovsolutions\n"
                                                   "After payment notify us via message like \"patreon member <your member name>\"\n"
                                                   "Plans:\n"
                                                   "3 urls - $2 per month"
                                                   "10 urls - $5 per month\n"
                                                   "20 urls - $10 per month\n"
                                                   "dedicated instance (1-2 min delay) - ask @m_m_pa\n"
                                                   "custom - ask @m_m_pa\n"
                                                   "\n",
                                  disable_web_page_preview=True,reply_markup=self.markup_keyboard(self.markup_commands))
        except Exception as e:
            self.logger.critical("Cant execute Upgrade command. " + str(e))
        return

    def markup_keyboard(self, list):
        markupkeyboard = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=7)
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
            try:
                self.bot.send_message(self.ADMIN_ID, "New message from " + str(message.chat.id) + "\n" + message.text)
                # check trial
                if self.is_trial_expired(message):
                    self.logger.debug("double - trial ends for user: " + str(message.chat.id))
                    self.bot.send_message(message.chat.id, text="Пробный период истек, чтобы продолжить работу, оформите подписку через команду /upgrade\n\n"
                                          "Trial period is expired. To continue please get subscription via /upgrade")
                    self.bot.send_message(self.ADMIN_ID, "Message after trial " + str(message.chat.id) + "\n" + message.text)
                if message.reply_to_message is not None:
                    # TODO Process reply message
                    return
                if message.text.startswith("/start"):
                    self.command_start(message)
                    self.db_execute("update salemon_bot_users set state = %s where user_id = %s", ("", message.chat.id),
                                    "Update State")
                    return
                if message.text.startswith("/help"):
                    self.command_help(message)
                    return
                if message.text.startswith("/donate"):
                    self.command_donate(message)
                    return
                if message.text.startswith("/usage"):
                    self.command_usage(message)
                    self.db_execute("update salemon_bot_users set state = %s where user_id = %s", ("", message.chat.id),
                                    "Update State")
                    return
                if message.text.startswith("/show"):
                    self.command_show(message)
                    return
                if message.text.startswith("/upgrade"):
                    self.command_upgrade(message)
                    return
                if message.text.startswith("/stop"):
                    self.command_stop(message)
                    return
                if message.text.startswith("/broadcast"):
                    if int(message.chat.id) == int(self.ADMIN_ID):
                        self.broadcast(message.text.replace("/broadcast ", ""))
                    else:
                        self.bot.reply_to(message, "You are not admin")
                    return
                if message.text.startswith("/"):
                    self.bot.reply_to(message, "Unknown command. Tap /help")
                    return
                if message.text.find("patreon") > -1:
                    self.bot.reply_to(message, "Thank you")
                    return
                if message.text.startswith("/add"):
                    self.command_add(message)
                    return

                # проверка на статусы:
                state = \
                self.db_query("select state from salemon_bot_users where user_id=%s", (message.chat.id,), "Get State")[0][0]

                # + проверили на урл и если да - вставлять .or validators.url(message.text)
                if state == "wait_url":
                    if self.add_url(message.chat.id, message.text):
                        self.db_execute("update salemon_bot_users set state = %s where user_id = %s", ("", message.chat.id),
                                        "Update State")
                        self.bot.reply_to(message, "Done!")
                        self.bot.send_message(self.ADMIN_ID, "New url: " + message.text)
                    else:
                        self.bot.reply_to(message,
                                          "Not a valid url or unsupported site\nExample: http://www.domain.com/search?q=test")
                    return

                if state.startswith("wait_subs_for_urlid"):
                    url_id = state[state.find(":") + 1:]
                    if self.set_subscription(url_id, message.text):
                        self.db_execute("update salemon_bot_users set state = %s where user_id = %s", ("", message.chat.id),
                                        "Update State")
                        self.bot.reply_to(message, "Done!")
                    else:
                        self.bot.reply_to(message, "Not a valid format for this Domain\nHelp: " + self.MAIN_HELP_LINK)
                    return

                # Если ничего не сработало
                # print(message)

                self.bot.reply_to(message, text="Tap command", reply_markup=self.markup_keyboard(self.markup_commands),
                                  parse_mode='Markdown')
            except Exception as e:
                self.logger.warning("Cant process message:" + str(message) + str(e))
                self.bot.reply_to(message, text="Unknown error. Tap command", reply_markup=self.markup_keyboard(self.markup_commands),
                                  parse_mode='Markdown')

    def handle_callback_messages(self, callback_message):
        # обязательный ответ в API
        self.bot.answer_callback_query(callback_message.id)

        # Разбор команд
        # команда удаления URL
        if callback_message.data == "delete":
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
                if len(self.db_query("select url_id from bots.salemon_engine_urls where url_id = %s", (url_id[0][0],),
                                     "Get UrlId")) < 1:
                    # нет такого URL
                    keys = ["/show actual URLs"]
                    self.bot.edit_message_text(chat_id=callback_message.message.chat.id,
                                               message_id=callback_message.message.message_id,
                                               text="Could not find URL.",
                                               reply_markup=self.inline_keyboard(keys), parse_mode='Markdown')
                    return
                else:
                    # запоминаем и ставим статус с ожиданием
                    self.db_execute("update salemon_bot_users set state = %s where user_id = %s",
                                    ("wait_subs_for_urlid:" + str(url_id[0][0]), callback_message.message.chat.id),
                                    "Update State")
                    self.bot.send_message(callback_message.message.chat.id, "Please provide new filter list..")
            return

        # subscription = self.db_query("select subscription from salemon_engine_urls where url_id = %s",(url_id[0][0]),"Get Subscription")
        # print(callback_message.data)

        return

    def new_user(self, user_id, user_name):
        trial_expired_time = str(datetime.now() + timedelta(days=self.TRIAL_DAYS))
        if len(self.db_query("select user_id from salemon_bot_users where user_id=%s", (user_id,),
                             "Check User exist")) > 0:
            return False
        # add user:
        elif self.db_execute("insert into salemon_bot_users (name,user_id,trial_expired_time) values (%s,%s,%s)", (user_name, user_id, trial_expired_time),
                             "Add new User"):
            return True
        else:
            return False

    def add_url(self, user_id, url):
        # убираем мобильную версию avito:
        url = url.replace("m.avito","avito")

        # проверяем, что это корректный URL
        if not validators.url(url):
            return False

        priority = 0

        # проверяем, есть ли  нас парсер для нее
        parsed_uri = urlparse(url)
        domain = '{uri.netloc}'.format(uri=parsed_uri)
        domain = domain.replace("www.","")
        if len(self.db_query("select parser_name from salemon_engine_parsers where domain = %s", (domain,),
                             "Check Domain")) < 1:
            return False

        if len(url) > 1000:
            return False

        # проверка на длину урла для avito
        #
        #

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

        if self.db_execute(
                "insert into salemon_engine_urls (url,user_id,tor_requirement,priority) values (%s,%s,%s,%s)",
                (url, user_id, tor_requirement, priority), "Add url"):
            return True
        else:
            return False

    def set_subscription(self, url_id, subscription):
        if subscription.find("|") >= 0:
            return False
        if self.db_execute("update salemon_engine_urls set subscription = %s where url_id = %s",
                           (subscription.replace("\n", "|"), url_id), "Update subscription"):
            return True
        else:
            return False

    def broadcast(self, message):
        for item in self.db_query("select user_id from salemon_bot_users where blocked = '0'", (), "Get all Users"):
            try:
                self.bot.send_message(item[0], message)
                self.logger.info("Successfully sent broadcast for user:" + str(item[0]))
            except Exception as e:
                self.logger.warning("Cant send broadcast message for user:" + str(item[0])+ "; " + str(e))
                self.db_execute("update salemon_bot_users set blocked = '1', reason = %s where user_id = %s", (str(e)[0:299],item[0]),"Broadcast() Set user Blocked")

    def is_trial_expired(self, message):
        user_properties = self.db_query("select full_user,trial_expired_time from salemon_bot_users where user_id=%s", (message.chat.id,), "Get user properties")
        try:
            full_user_flag = int(user_properties[0][0])
            trial_expired_time = user_properties[0][1]
    
            if full_user_flag == 0:
                self.logger.debug(str(trial_expired_time) + "-" + str(datetime.now())
                if trial_expired_time < datetime.now():
                    self.logger.debug("trial ends for user: " + str(message.chat.id))
                    return True
            return False
        except Exception as e:
            self.bot.send_message(self.ADMIN_ID, "Cant check trial for user: " + str(message.chat.id))
            return False

if __name__ == '__main__':
    dBot = SaleMonBot()
    dBot.run()
