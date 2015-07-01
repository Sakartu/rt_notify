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

        self.config = SafeConfigParser(defaults={'renotify_time': '60'})
        if os.path.isfile(config_path):
            # Load config file
            with open(config_path) as f:
                self.config.readfp(f)
        else:
            self.set_user_pass()
            self.set_url()
            self.save_config()

        renotify_time = int(self.config.get('main', 'renotify_time')) * 60
        self.tickets = expiringdict.ExpiringDict(max_len=100, max_age_seconds=renotify_time)
        self.debug = False
        rumps.debug_mode(self.debug)

    @rumps.clicked('Change user and password')
    def set_user_pass(self, _):
        w = rumps.Window('Please enter your username').run()
        if w.clicked:
            user = w.text
            self.config.set('main', 'user', w.text)

            w = rumps.Window('Please enter your password').run()
            if w.clicked:
                keyring.set_password(self.__class__.__name__, user, w.text)
        self.save_config()

    @rumps.clicked('Change RequestTracker URL')
    def set_url(self, _):
        w = rumps.Window('Please enter the RT url').run()
        if w.clicked:
            self.config.set('main', 'url', w.text)

    @rumps.clicked('Change renotify time (default 1 hr)')
    def set_renotify_time(self, _):
        w = rumps.Window('Please enter a new renotify time, in minutes').run()
        if w.clicked:
            try:
                self.config.set('main', 'renotify_time', w.text)

                old = self.tickets
                # Create a new expiring dict with the new time
                self.tickets = expiringdict.ExpiringDict(max_len=100, max_age_seconds=int(w.text) * 60)
                # Copy all old keys
                for k, v in old.items():
                    self.tickets[k] = v
            except ValueError:
                rumps.alert('Wrong renotify time', 'The given renotify time is not a valid integer!')

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


def main():
    setup_logging()
    logging.info('Starting RT monitor')
    RTNotifier().run()


if __name__ == '__main__':
    main()
