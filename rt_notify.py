#!/usr/bin/env python2
# -*- coding: utf8 -*-
from ConfigParser import SafeConfigParser
import os

from bs4 import BeautifulSoup
import keyring
import requests.exceptions
from pync import Notifier
import rumps
import xdg.BaseDirectory
import expiringdict
import requests
import logging
# noinspection PyUnresolvedReferences
from AppKit import NSSecureTextField
# noinspection PyUnresolvedReferences
from Foundation import NSMakeRect

__author__ = 'peter'


def setup_logging():
    """
    Setup logging
    """
    formatter = logging.Formatter('%(asctime)s (%(process)d:%(name)s) [ %(levelname)7s ] : %(message)s')
    rootlogger = logging.getLogger()

    consolehandler = logging.StreamHandler()
    consolehandler.setFormatter(formatter)

    rootlogger.addHandler(consolehandler)
    rootlogger.setLevel(logging.DEBUG)
    logging.getLogger("requests").setLevel(logging.WARNING)


class RTNotifier(rumps.App):
    CONFIG_NAME = 'rtnotifier.ini'

    def __init__(self):
        super(RTNotifier, self).__init__("RT Notifier", icon='57365.png')
        self.config = None

        # Set user/password/url, either by asking or by getting from the config
        xdg_base = xdg.BaseDirectory.load_first_config(self.__class__.__name__)
        config_path = os.path.join(xdg_base, RTNotifier.CONFIG_NAME) if xdg_base else ''

        self.config = SafeConfigParser()
        if os.path.isfile(config_path):
            # Load config file
            with open(config_path) as f:
                self.config.readfp(f)
        else:
            self.config.add_section('main')
            self.set_user_pass(None)
            self.set_url(None)
            self.set_renotify_time(None)
            self.save_config()

        renotify_time = self.config.getint('main', 'renotify_time') * 60
        self.tickets = expiringdict.ExpiringDict(max_len=100, max_age_seconds=renotify_time)
        self.debug = False
        rumps.debug_mode(self.debug)

    def set_user_pass(self, _):
        w = self.ask('Please enter your username')
        old_user = self.config.get('main', 'user')
        if w.clicked and w.text:
            user = w.text
            self.config.set('main', 'user', w.text)

            w = self.ask('Please enter your password', password=True)
            if w.clicked and w.text:
                keyring.set_password(self.__class__.__name__, user, w.text)
            else:
                self.config.set('main', 'user', old_user)
        self.save_config()

    def set_url(self, _):
        w = self.ask('Please enter the RT url')
        if w.clicked and w.text:
            self.config.set('main', 'url', w.text)
        self.save_config()

    def set_renotify_time(self, sender):
        w = self.ask('Please enter a new renotify time, in minutes')
        if w.clicked and w.text:
            try:
                int(w.text)
                self.config.set('main', 'renotify_time', w.text)
                sender.title = 'Change renotify time (now {} minutes)'.format(w.text)

                old = self.tickets
                # Create a new expiring dict with the new time
                self.tickets = expiringdict.ExpiringDict(max_len=100, max_age_seconds=int(w.text) * 60)
                # Copy all old keys
                for k, v in old.items():
                    self.tickets[k] = v
            except ValueError:
                rumps.alert('The given renotify time is not a valid integer!')
        self.save_config()

    @rumps.timer(600)
    def run_monitor(self, _):
        try:
            url = self.config.get('main', 'url')
            user = self.config.get('main', 'user')
            password = keyring.get_password(self.__class__.__name__, user)
            r = requests.get(url, auth=(user, password), timeout=3)
            soup = BeautifulSoup(r.text)
            tables = soup.find_all("table", {"class": "ticket-list collection-as-table"})

            owned = []
            unowned = None
            if len(tables):
                owned = [tables[0]]

            if len(tables) > 1:
                unowned = tables[1]

            if len(tables) > 2:
                owned += [tables[2]]

            for t in owned:
                self.process_table(self.tickets, t, url, user)

            if unowned:
                self.process_table(self.tickets, unowned, url, user, filter_owner=False)

        except requests.exceptions.RequestException:
            logging.warning("Could not connect to Request Tracker, trying again soon")
            pass

    def process_table(self, tickets, table, url, user, filter_owner=True):
        logging.debug('Processing table')
        last_update_idx, subject_idx = self.find_indexes(table)

        if not last_update_idx:
            return

        logging.debug('Found valid entries in table')
        for line in table.find_all("tr"):
            tds = line.find_all("td")
            if len(tds) > last_update_idx:
                ticketnr = int(tds[0].a.contents[0])
                subject = tds[subject_idx].a.contents[0]
                last_updated_by = tds[last_update_idx].contents[0]

                if filter_owner and last_updated_by == user:
                    continue

                if ticketnr not in tickets:
                    self.notify(url, "Ticket {} is new: '{}'", ticketnr, subject)
                    tickets[ticketnr] = last_updated_by
                elif filter_owner and last_updated_by != tickets[ticketnr]:
                    self.notify(url, "Ticket {} is updated: '{}'", ticketnr, subject)
                elif self.debug:
                    self.notify(url, "Ticket {} is triggered by debug: '{}'", ticketnr, subject)

    def get_config_path(self):
        xdg_base = xdg.BaseDirectory.load_first_config(self.__class__.__name__)
        return os.path.join(xdg_base, RTNotifier.CONFIG_NAME) if xdg_base else ''

    def save_config(self):
        config_path = self.get_config_path()

        with open(config_path, 'w') as f:
            self.config.write(f)

    def update_renotify_menu_item(self, text):
        for k, v in self.menu.items():
            if v.title.startswith('Change renotify time'):
                v.title = 'Change renotify time (now {} minutes)'.format(text)
                return

    @staticmethod
    def notify(url, msg, ticketnr, subject):
        msg = msg.format(ticketnr, subject)
        logging.info(msg)
        Notifier.notify(msg, title="Request Tracker", open=url + '/Ticket/Display.html?id={}'.format(ticketnr))

    @staticmethod
    def find_indexes(table):
        last_update_idx = 0
        subject_idx = 0
        for i, th in enumerate(table.tr.find_all("th")):
            if 'Last Updated By' in th.contents:
                last_update_idx = i
            if 'Subject' in th.contents:
                subject_idx = i
        return last_update_idx, subject_idx

    # noinspection PyProtectedMember
    @staticmethod
    def ask(message, password=False):
        dimensions = (320, 20)
        w = rumps.Window(title=message, dimensions=dimensions, cancel=True)
        if password:
            w._textfield = NSSecureTextField.alloc().initWithFrame_(NSMakeRect(0, 0, *dimensions))
            w._textfield.setSelectable_(True)
            w._alert.setAccessoryView_(w._textfield)

        return w.run()


def main():
    setup_logging()
    logging.info('Starting RT monitor')
    app = RTNotifier()
    app.menu = [
        rumps.MenuItem('Change user and password', callback=app.set_user_pass),
        rumps.MenuItem('Change RequestTracker URL', callback=app.set_url),
        rumps.MenuItem('Change renotify time (now {} minutes)'.format(app.config.getint('main', 'renotify_time')),
                       callback=app.set_renotify_time),
        None
    ]
    app.run()


if __name__ == '__main__':
    main()
