#!/usr/bin/env python3
# -*- coding: utf8 -*-
"""
Usage:
rt_notify [options] USERPASSFILE URL

Options:
USERPASSFILE            A file with your HTTP Basic Auth username and password, each on a separate line
URL                     The url of the Request Tracker homepage
--debug                 Start in debugging mode, which will send notifications for all tickets
--notify_timeout T      Wait T seconds before notifying about same ticket again. [default: 3600]
"""
import logging
from bs4 import BeautifulSoup

from docopt import docopt
from pync import Notifier
import requests
import requests.exceptions
import time
import expiringdict

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
    rootlogger.setLevel(logging.INFO)
    logging.getLogger("requests").setLevel(logging.WARNING)


def notify(args, msg, ticketnr, subject):
    msg = msg.format(ticketnr, subject)
    logging.info(msg)
    Notifier.notify(msg, title="Request Tracker", open=args['URL'] + '/Ticket/Display.html?id={}'.format(ticketnr))


def find_indexes(table):
    last_update_idx = 0
    subject_idx = 0
    for i, th in enumerate(table.tr.find_all("th")):
        if 'Last Updated By' in th.contents:
            last_update_idx = i
        if 'Subject' in th.contents:
            subject_idx = i
    return last_update_idx, subject_idx


def process_table(args, tickets, table, user, filter_owner=True):
    logging.debug('Processing table')
    last_update_idx, subject_idx = find_indexes(table)

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
                notify(args, "Ticket {} is new: '{}'", ticketnr, subject)
                tickets[ticketnr] = last_updated_by
            elif filter_owner and last_updated_by != tickets[ticketnr]:
                notify(args, "Ticket {} is updated: '{}'", ticketnr, subject)
            elif args['--debug']:
                notify(args, "Ticket {} is triggered by debug: '{}'", ticketnr, subject)


def main():
    args = docopt(__doc__)
    setup_logging()
    logging.info('Getting user/pass')
    user, passwd = [x.strip() for x in open(args['USERPASSFILE']).readlines() if x]
    logging.info('Starting RT monitor')
    tickets = expiringdict.ExpiringDict(max_len=100, max_age_seconds=int(args['--notify_timeout']))
    while True:
        try:
            r = requests.get(args['URL'], auth=(user, passwd), timeout=3)
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
                process_table(args, tickets, t, user)

            if unowned:
                process_table(args, tickets, unowned, user, filter_owner=False)

        except requests.exceptions.RequestException:
            logging.warning("Could not connect to Request Tracker, trying again soon")
            pass
        time.sleep(5 * 60)


if __name__ == '__main__':
    main()
