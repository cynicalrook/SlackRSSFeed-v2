import os
import json
import time
import re
import configparser
import feedparser
from datetime import datetime
from slackclient import SlackClient
from tinydb import TinyDB, Query
from urllib.parse import urlparse


# constants
RTM_READ_DELAY = 1 # 1 second delay between reading from RTM
EXAMPLE_COMMAND = "help"
MENTION_REGEX = "^<@(|[WU].+?)>(.*)"
starterbot_id = None
command_text = ['help', 'list feeds', 'list keywords', 'add keyword', 'add feed', 'remove keyword', 'remove feed']
feed_db = TinyDB('rsslist.json')

def get_keywords():
    with open('keywords.json') as keyword_file:
        data1 = json.load(keyword_file)
    s = set(data1)
    return s
    
def parse_bot_commands(slackbot_id, slack_events):
    """
        Parses a list of events coming from the Slack RTM API to find bot commands.
        If a bot command is found, this function returns a tuple of command and channel.
        If its not found, then this function returns None, None.
    """
    for event in slack_events:
        if event["type"] == "message" and not "subtype" in event:
            user_id, message = parse_direct_mention(event["text"])
            if user_id == slackbot_id:
                return message, event["channel"]
    return None, None

def parse_direct_mention(message_text):
    """
        Finds a direct mention (a mention that is at the beginning) in message text
        and returns the user ID which was mentioned. If there is no direct mention, returns None
    """
    matches = re.search(MENTION_REGEX, message_text)
    # the first group contains the username, the second group contains the remaining message
    return (matches.group(1), matches.group(2).strip()) if matches else (None, None)

def handle_command(slack_client, command, channel):
    """
        Executes bot command if the command is known
    """
    # Default response is help text for the user
    default_response = "Not sure what you mean. Try *{}*.".format(EXAMPLE_COMMAND)

    # Finds and executes the given command, filling in response
    response = ''
    # This is where you start to implement more commands!
    keywords = []
    split_payload = ''
    s = command.split()
    s_len = len(s)
    if s_len <= 1:
        split_command = 'help'
    else:
        split_command = (s[0].lower() + ' ' + s[1].lower())
    count = 2
    while count < s_len:
        split_payload = split_payload + s[count] + ' '
        count = count + 1
    split_payload = split_payload.strip()
    split_payload_lower = split_payload.lower()

    if split_command in command_text:
        if split_command in ('list keywords'):
            keywords = list(get_keywords())
            response = keywords
        elif split_command in ('add keyword'):
            keywords = list(get_keywords())
            if s[2].lower() in keywords:
                response = s[2] + ' is already in the keyword list!'
            else:
                keywords.append(s[2].lower())
                with open('keywords.json', 'w') as outfile:
                    json.dump(keywords, outfile, sort_keys=True, indent=4)
                response = 'added keyword ' + s[2].lower()
        elif split_command in ('remove keyword'):
            keywords = list(get_keywords()) 
            if s[2].lower() not in keywords:
                response = s[2] + ' is not in the keyword list!'
            else:
                keywords.remove(s[2].lower())
                with open('keywords.json', 'w') as outfile:
                    json.dump(keywords, outfile, sort_keys=True, indent=4)
                response = 'removed keyword ' + s[2].lower()
        elif split_command in ('list feeds'):
            numentries = len(feed_db)
            count = 0
            feeds_title = [r['feedtitle'] for r in feed_db]
            feeds_url = [r['url'] for r in feed_db]
            while count < numentries:
                response = response + (feeds_title[count] + '    ' + feeds_url[count] + '\n')
                count = count + 1
        elif split_command in ('remove feed'):
            feeds_title = split_payload
            search_feed = Query()
            search_result = feed_db.search(search_feed.feedtitle.matches(feeds_title, flags=re.IGNORECASE))
            if search_result != []:
                feed_db.remove(search_feed.feedtitle.matches(feeds_title, flags=re.IGNORECASE))
                response = feeds_title + ' removed!'
            else:
                response = feeds_title + ' is not in the feeds list!'
        elif split_command in ('add feed'):
            feed_rss = split_payload_lower.strip('<>')
            feed = feedparser.parse(feed_rss)
            try:
                feed_entries = feed.entries[1]   # Test for valid RSS feed
                search_feed = Query()
                search_result = feed_db.search(search_feed.url == feed_rss)
                if search_result != []:
                    response = feed.feed.title + ' (' + feed_rss + ') is already in the feed list!'
                else:   
                    feed_insert = {"feedtitle": feed.feed.title, "url": feed_rss, "lastupdate": datetime.utcnow().strftime('%a, %d %b %Y %H:%M:%S +0000')}
                    feed_db.insert(feed_insert)
                    response = feed.feed.title + ' successfully added!'
            except IndexError:
                response = "I'm sorry, I don't recognize that as a valid RSS feed.  Please check the site."
        elif split_command in ('help'):
            default_response = 'Commands:\nlist feeds\nlist keywords\nadd feed <RSS feed URL>\nadd keyword <keyword>\nremove feed <feed name from *list feeds* command>\nremove keyword <keyword>'
    else:
        response = 'Commands:\nlist feeds\nlist keywords\nadd feed <RSS feed URL>\nadd keyword <keyword>\nremove feed <feed name from *list feeds* command>\nremove keyword <keyword>'


    # Sends the response back to the channel
    slack_client.api_call(
        "chat.postMessage",
        channel=channel,
        text=response or default_response
    )

def load_config(config_file, config_section):
#    dir_path = os.path.dirname(os.path.relpath('config.ini'))
    dir_path = os.path.dirname(os.path.realpath(__file__))
#    dir_path = os.path.abspath('.')
    if os.path.isfile(dir_path + '/' + config_file):
        config = configparser.ConfigParser()
        config.read(config_file)
        slack_token = config.get(config_section, 'token')
    else:
        slack_token = os.environ['token']
    return slack_token

def main():
    config_file = 'config.ini'
    config_section = 'dev'
    slack_token = load_config(config_file, config_section)
    slack_client = SlackClient(slack_token)
    if slack_client.rtm_connect(with_team_state=False, auto_reconnect=True):
        print("Feedbot connected and running!")
        # Read bot's user ID by calling Web API method `auth.test`
        slackbot_id = slack_client.api_call("auth.test")["user_id"]
        while True:
            command, channel = parse_bot_commands(slackbot_id, slack_client.rtm_read())
            print(slack_client.rtm_read())
            if command:
                handle_command(slack_client, command, channel)
            time.sleep(RTM_READ_DELAY)
    else:
        print("Connection failed. Exception traceback printed above.")

if __name__ == "__main__":
    main()
