import argparse
import fileinput
import math
import os
import sys
from signal import signal, SIGPIPE, SIG_DFL
from urllib.parse import urlparse

import apachelogs
import maxminddb
import pandas as pd
from tld import get_fld

import pdb

signal(SIGPIPE,SIG_DFL)

class Analyzer:

    def __init__(self, maxmind_db=None, verbose=False, top_k=5, web_site='example.com'):
        self.iplookup = self._init_ip_lookup(maxmind_db)
        self.verbose = verbose
        self.top_k = top_k
        self.web_site = web_site

    def get_location_en(self, remote_host):
        try:
            geo = self.iplookup(remote_host)
            city = geo['city']['names']['en']
            country = geo['country']['names']['en']
            return f'{city},{country}'
        except:
            return None

    def _init_ip_lookup(self, maxmind_db):
        try:
            self.maxmind_reader = maxminddb.open_database(maxmind_db)
            return self.maxmind_reader.get
        except:
            self.maxmind_reader = None
            return lambda x: None

    def _json(self, e):
        common = {
            'remote_host': e.remote_host,
            'request_time': e.request_time,
            'request_line': e.request_line,
            'final_status': e.final_status,
            'bytes_sent': e.bytes_sent
        }
        headers = e.headers_in
        return {**common, **headers}

    def _get_entries(self, logs):
        parser = apachelogs.LogParser(apachelogs.COMBINED)
        with fileinput.input(logs) as fi:
            for line in fi:
                try:
                    e = parser.parse(line.strip())
                    yield self._json(e)
                except Exception as e:
                    if self.verbose:
                        sys.stderr.write('Error parsing line\n')

    def _get_fld(self, url):
        try:
            return get_fld(url)
        except:
            return url

    def analyze(self, logs):


        entries = self._get_entries(logs)
        df = pd.DataFrame(entries)

        # extract fld
        df['referer_fld'] = df[~df.Referer.isnull()].Referer.apply(self._get_fld)
        df['date'] = df.request_time.dt.date
        df['hour'] = df.request_time.dt.hour

        # calc days
        total_seconds = (df.request_time.max() - df.request_time.min()).total_seconds()
        distinct_dates = df.date.unique()
        n_distinct_dates = len(distinct_dates)
        # detect robots
        robots = df[df.request_line.str.contains('/robots.txt')].remote_host.unique()
        robot_requests = df[df.remote_host.isin(robots)]
        # detect users (not robots)
        humans = df[~df.remote_host.isin(robots)].remote_host.unique()
        human_requests = df[(df.remote_host.isin(humans)) & (~df.request_line.str.contains('favicon'))]

        # calculate humans per day
        humans_per_day = human_requests.loc[:, ['date', 'remote_host']].drop_duplicates().groupby('date').size()

        print('summary:'.upper())
        print(f'- distinct days: {n_distinct_dates}')
        print(f'- first date: {df.date.min()}')
        print(f'- last date: {df.date.max()}')
        print(f'- total humans seen: {len(humans)}')
        print(f'- total robots seen: {len(robots)}')
        print(f'- average humans/day: {humans_per_day.mean()}')
        print(f'- maximum humans/day: {humans_per_day.max()}')

        print(f'top {self.top_k} referers:'.upper())
        true_referers = human_requests[human_requests.referer_fld.notnull()]
        true_referers = true_referers[~true_referers.referer_fld.str.endswith(self.web_site)]
        top_referers = true_referers.groupby('referer_fld').size().sort_values(ascending=False).head(self.top_k)
        #pdb.set_trace()
        for referer_fld,count in top_referers.items():
            perc = round(100*count/len(true_referers), 2)
            print(f'- {referer_fld}  {perc}%')


        print(f'top {self.top_k} busiest hours:'.upper())
        top_hours = human_requests.groupby('hour').size().sort_values(ascending=False).head(self.top_k)
        for hour,count in top_hours.items():
            perc = round(100*count/len(human_requests), 2)
            print(f'- {hour}  {perc}%')

        print(f'top {self.top_k} user location:'.upper())
        # extract geography
        locations = pd.Series(humans).apply(self.get_location_en)
        top_locations = locations.value_counts().head(self.top_k)
        #pdb.set_trace()
        for location, count in top_locations.items():
            perc = round(100*count/len(humans), 2)
            print(f'- {location}  {perc}%')

        if self.verbose:
            print(df.dtypes)
            print(df)



if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('-w', '--web-site', default='example.com', help='First-level domain of web site, e.g. example.com, used to filter referers')
    parser.add_argument('logs', nargs='*', help='Input logs to read (file or stdin)')
    parser.add_argument('-m', '--maxmind-db', default=None, help='Location of maxmind database (*.mmdb)')
    parser.add_argument('-v', '--verbose', action='store_true', help='Verbose output')
    parser.add_argument('-k', '--top-k', default=10, type=int, help='Number of items to show in TOP section')
    args = parser.parse_args()
    analyzer = Analyzer(maxmind_db=args.maxmind_db, verbose=args.verbose, top_k=args.top_k, web_site=args.web_site)
    analyzer.analyze(args.logs)
