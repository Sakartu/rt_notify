#!/usr/bin/env python3
# -*- coding: utf8 -*-
"""
Usage:
rt_notify [options] USERPASSFILE

Options:
--debug     Start in debugging mode, which will send notifications for all tickets
"""
import logging
from bs4 import BeautifulSoup

from docopt import docopt
from pync import Notifier
import requests
import requests.exceptions
import time

__author__ = 'peter'


URL = 'http://intake.surv.intern/'


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


def main():
    args = docopt(__doc__)
    setup_logging()
    logging.info('Getting user/pass')
    user, passwd = [x.strip() for x in open(args['USERPASSFILE']).readlines() if x]
    logging.info('Starting RT monitor')
    while True:
        try:
            r = requests.get(URL, auth=(user, passwd), timeout=3)
            soup = BeautifulSoup(r.text)
            tables = soup.find_all("table", {"class": "ticket-list collection-as-table"})
            for table in tables:
                logging.debug('Found table')
                last_update_idx = 0
                subject_idx = 0
                for i, th in enumerate(table.tr.find_all("th")):
                    if 'Last Updated By' in th.contents:
                        last_update_idx = i
                    if 'Subject' in th.contents:
                        subject_idx = i

                if not last_update_idx:
                    continue

                logging.debug('Found valid entries in table')
                for line in table.find_all("tr"):
                    tds = line.find_all("td")
                    if len(tds) > last_update_idx and (user not in tds[last_update_idx] or args['--debug']):
                        ticketnr = int(tds[0].a.contents[0])
                        subject = tds[subject_idx].a.contents[0]
                        msg = "Ticket {} is new: '{}'".format(ticketnr, subject)
                        logging.info(msg)
                        Notifier.notify(msg, title="Request Tracker")
        except requests.exceptions.RequestException:
            logging.warning("Could not connect to Request Tracker, trying again soon")
            pass
        time.sleep(5 * 60)


if __name__ == '__main__':
    main()
