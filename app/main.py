#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import datetime as dt
from itertools import count
import os
import re
import sys
from distutils.util import strtobool
from logging import basicConfig, getLogger

from playwright.sync_api import sync_playwright

JST = dt.timezone(dt.timedelta(hours=+9), 'JST')
USER_AGENT = 'Mozilla/5.0 (Windows NT 10.0; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36'
PAGE_URL = os.environ['PAGE_URL']
EVENT_LOG = 'event.log'

LOG_LEVEL = os.environ.get('LOG_LEVEL', 'INFO').upper()
if LOG_LEVEL not in ('DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'):
    LOG_LEVEL = 'INFO'
basicConfig(level=LOG_LEVEL, stream=sys.stderr)
logger = getLogger(__name__)

HEADLESS = bool(strtobool(os.getenv("HEADLESS", "true")))


def get_post_date(text: str) -> dt.datetime | None:
    m: re.Match
    if m := re.match(r'(?P<num>\d+)(?P<unit>秒|分|時間|日)前', text):
        post_dt = dt.datetime.now(JST)
        num = int(m['num'])
        match m['unit']:
            case '秒':
                post_dt -= dt.timedelta(seconds=num)
            case '分':
                post_dt -= dt.timedelta(minutes=num)
            case '時間':
                post_dt -= dt.timedelta(hours=num)
            case '日':
                post_dt -= dt.timedelta(days=num)
        return post_dt
    if m := re.match(r'((?P<year>\d+)年)?(?P<month>\d+)月(?P<date>\d+)日', text):
        year = int(m['year'] or dt.datetime.now(JST).year)
        month = int(m['month'])
        date_ = int(m['date'])
        return dt.datetime(year, month, date_, tzinfo=JST)
    return None

def get_event_date(text: str, post_dt: dt.datetime) -> dt.date | None:
    if m := re.search(r'(?P<month>\d+)月(?P<date>\d+)日.*室料半額', text):
        month, date_ = map(int, m.group('month', 'date'))
        event_date = dt.date(post_dt.year, month, date_)
        if event_date < post_dt.date():
            event_date = dt.date(post_dt.year+1, month, date_)
        return event_date
    return None


def main():
    logger.debug('start main')
    with sync_playwright() as p:
        logger.debug('start playwright')
        browser = p.chromium.launch(headless=HEADLESS)
        context_params = {
            'user_agent': USER_AGENT,
            'locale': 'ja-JP',
            'viewport': { 'width': 500, 'height': 5000 }
        }
        context = browser.new_context(**context_params)
        # context.set_default_timeout(10000)
        context.route("**/*", lambda route: route.abort() if route.request.resource_type in "image" else route.continue_())
        page = context.new_page()
        logger.debug('start page')

        page.goto(PAGE_URL, wait_until="domcontentloaded")

        page.wait_for_selector('[aria-label="閉じる"]').click()

        for i in range(1, 20):
            el = page.wait_for_selector(f'[aria-posinset="{i}"]')
            date_text_query = ':not([data-ad-preview="message"]) a[aria-label][href^="https://www.facebook.com/karaoke.utahiroba/posts/"]'
            date_text = el.wait_for_selector(date_text_query).text_content()
            message_text = el.wait_for_selector('[data-ad-preview="message"]').text_content()
            
            logger.info(f'{date_text=}')
            logger.debug(f'{message_text=}')
            
            post_dt = get_post_date(date_text)
            event_date = post_dt and get_event_date(message_text, post_dt)
            if event_date is None:
                logger.info('skip post')
            else:
                logger.info(f'{event_date=}')
            # elif event_date >= dt.date.today():
            #     # update_event_log(event_date)
            #     logger.info('update event log')
            # else:
            #     logger.info('event date is past')
            #     break
            el.evaluate('el=>el.scrollIntoView(true)')
            

        browser.close()


if __name__ == '__main__':
    main()
