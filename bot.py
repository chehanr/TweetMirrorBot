#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""A Reddit bot that mirrors images from tweets (by /u/chehanr)."""

import datetime
import logging
import os
import re
import sys
import textwrap

import praw
import pyimgur
import redis
import requests
import tweepy

CWD = os.getcwd()
PATH = CWD + '/'

REDIS_URL = os.getenv('REDISTOGO_URL', 'REDIS://localhost:6379')
REDDIT_CLIENT_ID = os.getenv('REDDIT_CLIENT_ID')
REDDIT_CLIENT_SECRET = os.getenv('REDDIT_CLIENT_SECRET')
REDDIT_PASSWORD = os.getenv('REDDIT_PASSWORD')
REDDIT_REDIRECT_URL = os.getenv('REDDIT_REDIRECT_URL')
REDDIT_USER_AGENT = os.getenv('REDDIT_USER_AGENT')
REDDIT_USER_NAME = os.getenv('REDDIT_USER_NAME')
TWITTER_CONSUMER_KEY = os.getenv('TWITTER_CONSUMER_KEY')
TWITTER_CONSUMER_SECRET = os.getenv('TWITTER_CONSUMER_SECRET')
TWITTER_ACCESS_TOKEN_KEY = os.getenv('TWITTER_ACCESS_TOKEN_KEY')
TWITTER_ACCESS_TOKEN_SECRET = os.getenv('TWITTER_ACCESS_TOKEN_SECRET')
IMGUR_CLIENT_ID = os.getenv('IMGUR_CLIENT_ID')

REPLY_FOOTER = (
    'beep^boop | [source](https://github.com/chehanr/TweetMirrorBot/ "Github")'
    ' | [report issue](https://www.reddit.com/message/compose/?to=TweetMirrorBot&subject=issue_report&message=[enter_issue] "Report issue")'
    ' | [contact](https://www.reddit.com/user/chehanr/ "/u/chehanr")'
)

REDIS = redis.from_url(REDIS_URL)

REDDIT_API = praw.Reddit(client_id=REDDIT_CLIENT_ID,
                         client_secret=REDDIT_CLIENT_SECRET,
                         password=REDDIT_PASSWORD,
                         redirect_uri=REDDIT_REDIRECT_URL,
                         user_agent=REDDIT_USER_AGENT,
                         username=REDDIT_USER_NAME)

TWITTER_AUTH = tweepy.OAuthHandler(
    TWITTER_CONSUMER_KEY, TWITTER_CONSUMER_SECRET)
TWITTER_AUTH.set_access_token(
    TWITTER_ACCESS_TOKEN_KEY, TWITTER_ACCESS_TOKEN_SECRET)
TWITTER_API = tweepy.API(TWITTER_AUTH)

IMGUR_API = pyimgur.Imgur(IMGUR_CLIENT_ID)


class GenerateReply:
    """Generate a reply.

    :param tweet: Tweet object.
    """

    def __init__(self, tweet):
        self._tweet = tweet

    def imgur(self, urls):
        """Generate submission reply with imgur template."""
        header_images = ''
        reply_body = ''
        date_time = datetime.datetime.strptime(
            str(self._tweet.created_at), '%Y-%m-%d  %H:%M:%S')

        for i, imgur_image in enumerate(urls):
            i += 1
            header_images += ('# [**Imgur mirror image%(index)s**](%(imgur)s "Imgur mirror image%(index)s")\n' % {
                'index': str(i).rjust(2) if len(urls) > 1 else '',
                'imgur': imgur_image
            })

        reply_body += ('%s' % (header_images.strip()))
        reply_body += '\n'
        # TODO Add bad chars to escape.
        reply_body += ('"%s"\n' %
                       (self._tweet.full_text.strip().replace('#', '\\#')))
        reply_body += '\n'
        reply_body += ('~ %(user_name)s ([@%(screen_name)s](https://twitter.com/%(screen_name)s/ "Twitter profile")) %(is_verified)s\n' % {
            'user_name': self._tweet.user.name.strip(),
            'screen_name': self._tweet.user.screen_name.strip(),
            'is_verified': '^([verified])' if self._tweet.user.verified else ''})
        reply_body += '\n'
        reply_body += ('^(Tweeted on %(date)s at %(time)s)\n' % {
            'date': date_time.date(),
            'time': date_time.time()
        })
        reply_body += '\n'
        reply_body += ('&nbsp;\n')
        reply_body += '\n\n'
        reply_body += ('****\n')
        reply_body += ('%s' % (REPLY_FOOTER.strip()))

        return reply_body


class UploadTo:
    """Upload media to host."""
    @classmethod
    def imgur(cls, url, imgur_title, imgur_desc):
        """Upload media to imgur"""
        upload = IMGUR_API.upload_image(
            url=url, title=imgur_title, description=imgur_desc)
        return upload.link

    @classmethod
    def streamable(cls, url):
        """Upload media to streamable"""
        return url


class HasVisited:
    """Check if the bot has visited the submission."""
    @classmethod
    def redis_check(cls, key):
        """Return ``True`` if ``key`` exist in redis DB."""
        if REDIS.exists(key):
            return True

    @classmethod
    def redis_set(cls, key, value):
        """Set ``key`` with ``value`` in redis DB."""
        REDIS.set(key, value)

    @classmethod
    def check_comments(cls, submission):
        """Check within ``submission`` comment if already replied."""
        try:
            _submission = REDDIT_API.submission(submission.id)
            _submission.comments.replace_more(limit=0)
            for comment in _submission.comments:
                if comment.author == REDDIT_API.user.me():
                    return True
        except Exception:
            return False


class Regex:
    """Handle Regex work."""

    def __init__(self):
        self.twitter_com_regex = r'^https?:\/\/twitter\.com\/(?:#!\/)?(\w+)\/status(es)?\/(\d+)'
        # t.co just in case  (not allowed on reddit.)
        self.t_co_regex = r'^https?:\/\/t\.co\/(\w+)'

    def is_twitter_url(self, url):
        """Return ``True`` if is twitter url."""
        if re.match(self.twitter_com_regex, url):
            return True
        elif re.match(self.t_co_regex, url):
            return True

    def tweet_status_id(self, twitter_url):
        """Return status ID of ``twitter_url``."""
        if re.match(self.twitter_com_regex, twitter_url):
            status_id = re.search(self.twitter_com_regex, twitter_url).group(3)
        elif re.match(self.t_co_regex, twitter_url):
            response = requests.get(twitter_url)
            if response.history:
                status_id = self.tweet_status_id(response.twitter_url)
        return status_id


class TweetStatus:
    """Handle tweepy API.

    :param tweet_status_id: Status ID of the tweet.
    """

    def __init__(self, tweet_status_id):
        self.tweet = TWITTER_API.get_status(
            tweet_status_id, tweet_mode='extended')
        self.media_urls_list = []

    def media_url_type(self):
        """Return the media type of ``Tweet()``."""
        media_type = None
        if hasattr(self.tweet, 'extended_entities'):
            for image in self.tweet.extended_entities.get('media', []):
                if 'photo' in image['type']:
                    media_type = 'photo'
                if 'animated_gif' in image['type']:
                    media_type = 'animated_gif'
                if 'video' in image['type']:
                    media_type = 'video'
        elif hasattr(self.tweet, 'entities'):
            for image in self.tweet.entities.get('media', []):
                if '/media/' in image['media_url']:
                    media_type = 'photo'
        return media_type

    def get_photo(self):
        """Return a photo list of ``Tweet()``."""
        if hasattr(self.tweet, 'extended_entities'):
            for image in self.tweet.extended_entities.get('media', []):
                self.media_urls_list.append(image['media_url'])
        return self.media_urls_list

    def get_animated_gif(self):
        """Return a animated_gif list of ``Tweet()``."""
        if hasattr(self.tweet, 'extended_entities'):
            for image in self.tweet.extended_entities.get('media', []):
                for gif_varient in image['video_info'].get('variants'):
                    if 'video/mp4' in gif_varient['content_type']:
                        self.media_urls_list.append(gif_varient['url'])
        return self.media_urls_list

    def get_video(self):
        """Return a video list of ``Tweet()``."""
        if hasattr(self.tweet, 'extended_entities'):
            for image in self.tweet.extended_entities.get('media', []):
                for video_varient in image['video_info'].get('variants'):
                    if 'video/mp4' in video_varient['content_type']:
                        self.media_urls_list.append(video_varient['url'])
        return self.media_urls_list


def post_reply(tweet_status_id, submission):
    """"Post the reply to ``submission`` with ``tweet_status_id``."""
    tweet_status = TweetStatus(tweet_status_id)
    if tweet_status.media_url_type() == 'photo':
        imgur_url_list = []
        imgur_title = 'Tweet by @%s' % (tweet_status.tweet.user.name)
        imgur_desc = (
            'Image mirrored by /u/TweetMirrorBot (https://www.reddit.com/u/TweetMirrorBot) (by /u/chehanr).')
        if not HasVisited.check_comments(submission):
            try:
                for photo in tweet_status.get_photo():
                    imgur_url_list.append(UploadTo.imgur(
                        photo, imgur_title, imgur_desc))
                generated_reply = GenerateReply(
                    tweet_status.tweet).imgur(imgur_url_list)
            except Exception as err:
                logging.exception('failed to upload because %s', err)
            else:
                try:
                    submission.reply(generated_reply)
                except Exception as err:
                    logging.exception('failed to reply because %s', err)
                else:
                    HasVisited.redis_set(submission.id, tweet_status_id)
                    message = 'processed submission %s on /r/%s.' % (
                        submission.id, submission.subreddit)
                    sys.stdout.writelines('%s \n' % (message))
                    logging.info(message)
        else:
            HasVisited.redis_set(submission.id, tweet_status_id)
            message = 'reply found in submission %s in /r/%s, skipping...' % (
                submission.id, submission.subreddit)
            sys.stdout.writelines('%s \n' % (message))
            logging.info(message)


def main():
    """
    Usage: :

        >> > Add subreddits to "subreddits.txt" and
        >> > use '#' to comment out unwanted entries.

        >> > Add subreddits to "blacklist.txt" to
        >> > ignore them while monitoring "/r/all".
    """
    try:
        with open(PATH + 'blacklist.txt', 'r') as file:
            blacklist = [line.rstrip().lower() for line in file]
    except FileNotFoundError as err:
        logging.error(err)
    else:
        try:
            with open(PATH + 'subreddits.txt') as file:
                lines = filter(None, (line.rstrip() for line in file))
                subreddits = '+'.join(line[1] for line in enumerate(lines)
                                      if not line[1].startswith('#'))
                if subreddits:
                    message = 'checking subreddits %s ...' % (subreddits)
                    sys.stdout.writelines('%s \n' % (message))
                    logging.info(message)
                    for submission in REDDIT_API.subreddit(subreddits).new():
                        tweet_status_ids = []
                        if not submission.subreddit.display_name.lower() in blacklist:
                            if not HasVisited.redis_check(submission.id):
                                if Regex().is_twitter_url(submission.url):
                                    tweet_status_ids.append(
                                        Regex().tweet_status_id(submission.url))
                                if tweet_status_ids:
                                    for tweet_status_id in tweet_status_ids:
                                        post_reply(tweet_status_id, submission)
                            else:
                                message = 'submission %s in /r/%s already processed, skipping...' % (
                                    submission.id, submission.subreddit)
                                sys.stdout.writelines('%s \n' % (message))
                                logging.info(message)

        except FileNotFoundError as err:
            logging.error(err)


if __name__ == '__main__':
    main()
