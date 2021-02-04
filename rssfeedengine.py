import sys
import feedparser
import requests
import os
import inspect
import configparser
import json
import re
from datetime import datetime
from datetime import timezone
from pathlib import Path
from shutil import copy2
#from slackclient import SlackClient    old api
from slack_sdk import WebClient
from tinydb import TinyDB, Query

feed_db = TinyDB('rsslist.json')
slack_channel = "GDQ7JPD8U"

def get_keywords():
    with open('keywords.json') as keyword_file:
        data1 = json.load(keyword_file)
    s = set(data1)
    return s

def post_lastUpdate(url, lastupdate):
    try:
        date_formatted = datetime.strftime(lastupdate, '%a, %d %b %Y %H:%M:%S %z')
    except TypeError:
        if lastupdate[-1:] != 'T':
            date_formatted = lastupdate
        else:
            date_formatted = lastupdate[:-3] + '+0000'
    feed_search = Query()
    feed_db.update({'lastupdate': date_formatted}, feed_search.url == url)

def post_to_slack(slack_client, newposts):
    i = 0
    newposts.reverse()
    listsize = len(newposts)
    while i < listsize:
#        slack_client.api_call("chat.postMessage", channel=slack_channel, text=newposts[i], as_user = True)   old api call
        slack_client.chat_postMessage(channel=slack_channel, text=newposts[i])
        i = i + 1

def getfeed(urlstring, last_update_obj):
    newposts_list = []
    newposts_list_date = []
    d = feedparser.parse(urlstring)
    numentries = len(d.entries)
    last_update = datetime.strptime(last_update_obj, '%a, %d %b %Y %H:%M:%S %z')
    keywords = get_keywords()
    count = 0
    while count < numentries :
        try:
            published_date = datetime.strptime(d.entries[count].published, '%a, %d %b %Y %H:%M:%S %z')
        except ValueError:
            published_date = datetime.strptime(d.entries[count].published, '%a, %d %b %Y %H:%M:%S %Z')
            published_date = published_date.replace(tzinfo = timezone.utc)
        if published_date > last_update :    
            linktext = d.entries[count].title
            linktext_lower = linktext.lower()
            linksplit_lower = set(re.sub("[^a-zA-Z ]+", "", linktext_lower).split())
            keywords_lower = set(map(lambda x: x.lower(), keywords))
            if (linksplit_lower & keywords_lower) :
                newposts_list.append(d.entries[count].link)             # create post list
                newposts_list_date.append(published_date)
        else:
            break
        count = count + 1
    try:
        return newposts_list, newposts_list_date[0]
    except IndexError:
        return newposts_list, d.entries[0].published

def load_config(config_file, config_section):
    dir_path = os.path.dirname(os.path.realpath(__file__))
    if os.path.isfile(dir_path + '/' + config_file):
        config = configparser.ConfigParser()
        config.read(config_file)
        slack_token = config.get(config_section, 'token')
    else:
        slack_token = os.environ['token']
    return slack_token

def main():
    """
    Initialize required data files
    """
    try:
        init_file = open('keywords.json', 'r')
        init_file.close()
    except IOError:
        copy2('keywords.base', 'keywords.json')
    try:
        init_file = open('rsslist.json', 'r')
        init_file.close()
    except IOError:
        copy2('rsslist.base', 'rsslist.json')
    

    config_file = 'config.ini'
    config_section = 'dev'
    slack_token = load_config(config_file, config_section)
    slack_client = WebClient(slack_token)
    feed_count = len(feed_db)
    feed_counter = feed_count
    while feed_counter > 0:
        url = feed_db.get(doc_id = feed_counter)['url']
        last_update_obj = feed_db.get(doc_id = feed_counter)['lastupdate']
        post_list, published_date = getfeed(url, last_update_obj)
        feed_counter = feed_counter - 1
        print(post_list)
        post_lastUpdate(url, published_date)
        post_to_slack(slack_client, post_list)

if __name__ == '__main__':
    main()
