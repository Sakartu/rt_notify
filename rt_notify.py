#!/usr/bin/env python3
# -*- coding: utf8 -*-
"""
Usage:
rt_notify USERPASSFILE

Options:
"""
import logging
from bs4 import BeautifulSoup

from docopt import docopt
from pync import Notifier
import requests
import time

__author__ = 'peter'


URL = 'http://intake.surv.intern/'


def main():
    args = docopt(__doc__)
    logging.basicConfig()
    user, passwd = [x.strip() for x in open(args['USERPASSFILE']).readlines() if x]
    while True:
        r = requests.get(URL, auth=(user, passwd))
        soup = BeautifulSoup(r.text)
        tables = soup.find_all("table", {"class": "ticket-list collection-as-table"})
        for table in tables:
            last_update_idx = 0
            subject_idx = 0
            for i, th in enumerate(table.tr.find_all("th")):
                if 'Last Updated By' in th.contents:
                    last_update_idx = i
                if 'Subject' in th.contents:
                    subject_idx = i

            if not last_update_idx:
                continue

            for line in table.find_all("tr"):
                tds = line.find_all("td")
                if len(tds) > last_update_idx and user in tds[last_update_idx]:
                    ticketnr = int(tds[0].a.contents[0])
                    subject = tds[subject_idx].a.contents[0]
                    msg = "Ticket {} is new: '{}'".format(ticketnr, subject)
                    logging.debug(msg)
                    Notifier.notify(msg, title="Request Tracker")
        time.sleep(5 * 60)


if __name__ == '__main__':
    main()
