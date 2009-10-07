#!/usr/bin/env python
#
# Copyright 2009 Facebook
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.

import logging
import tornado.auth
import tornado.escape
import tornado.httpserver
import tornado.ioloop
import tornado.options
import tornado.web
import tornado.autoreload
import tornado.locale
import os.path
import uuid
from tornado.options import define, options

define("port", default=80, help="run on the given port", type=int)
define("twitter_consumer_key", help="The consumer key for Twitter", default="qnBv8zGhDrzIyeIjc0oP4w")
define("twitter_consumer_secret", help="The consumer secret", default="dFLdn9fLtgSMG8Du9iPfch8DdLaDH1iEqVeJ2Jsf27s")

define("facebook_api_key", help="your Facebook application API key", default="903ce065e49369cce378b9bdc4e8d16a")
define("facebook_secret", help="your Facebook application secret", default="3d403f8bf5e3d6c6177e0baf906dc0a1")

i = 0
POLL_INTERVAL = 60

class Application(tornado.web.Application):
    def __init__(self):
        handlers = [
            (r"/", MainHandler),
            (r"/auth/twitter", AuthTwitterHandler),
            (r"/auth/facebook", AuthFacebookHandler),
            (r"/auth/logout", AuthLogoutHandler),
            (r"/a/twitter/timeline", TwitterTimelineHandler),
            (r"/a/twitter/timeline/previous", TwitterPreviousHandler),
            (r"/a/twitter/status", TwitterStatusHandler),
            (r"/a/twitter/status/last", TwitterStatusLastHandler),
            (r"/a/facebook/stream", FacebookStreamHandler),
            (r"/a/facebook/timeline/previous", FacebookPreviousHandler),
            (r"/a/facebook/status", FacebookStatusHandler),
            (r"/a/facebook/status/last", FacebookStatusLastHandler),
        ]
        settings = dict(
            twitter_consumer_key = options.twitter_consumer_key,
            twitter_consumer_secret = options.twitter_consumer_secret,
            facebook_api_key=options.facebook_api_key,
            facebook_secret=options.facebook_secret,
            ui_modules= {'Post': PostModule, 'Tweet': TweetModule},
            cookie_secret="43oETzKXQAGaYdkL5gEmGeJJFuYh7EQnp2XdTP1o/Vo=",
            login_url="/",
            template_path=os.path.join(os.path.dirname(__file__), "templates"),
            static_path=os.path.join(os.path.dirname(__file__), "static"),
            xsrf_cookies=True,
            debug=True
        )
        tornado.web.Application.__init__(self, handlers, **settings)


class BaseHandler(tornado.web.RequestHandler):
    def get_current_twitter_user(self):
        user_json = self.get_secure_cookie("twitter_user")
        if not user_json: return None
        return tornado.escape.json_decode(user_json)

    def save_current_twitter_user(self, user):
        self.set_secure_cookie("twitter_user", tornado.escape.json_encode(user))

    def get_current_facebook_user(self):
        user_json = self.get_secure_cookie("facebook_user")
        if not user_json: return None
        return tornado.escape.json_decode(user_json)

    def save_current_facebook_user(self, user):
        self.set_secure_cookie("facebook_user", tornado.escape.json_encode(user))

class TweetMixin(object):
    waiters = {}
    polls = {}
    since_ids = {}

    def get_current_user(self):
        return self.get_current_twitter_user()

    def poll_twitter(self):
        user = self.get_current_twitter_user()
        import time
        cls = TweetMixin
        since_id = cls.since_ids.get(user['id'], 1)
        # print str(user['id']) + ' | since_id ' + str(since_id)
        timeout = cls.polls.get(user['id'], None)
        # Start polling if they havent already!
        if not timeout or timeout.deadline < time.time() and not self._finished:
            timeout = tornado.ioloop.IOLoop.instance().add_timeout(time.time() + POLL_INTERVAL, self.poll_twitter)
        self.polls[user['id']] = timeout
        print self.polls
        args = dict(path = "/statuses/friends_timeline",
                             access_token=user["access_token"],
                             since_id = since_id,
                             count=30,
                             callback = self.async_callback(self.poll_twitter_cb))
        self.twitter_request(**args)

    def poll_twitter_cb(self, tweets):
        if tweets:
            user = self.get_current_twitter_user()
            print str(user['id']) + " | retrieved " + str(len(tweets))
            cls = TweetMixin
            text = ""
            for tweet in tweets:
                # print tweet['id']
                text += self.render_string("modules/tweet.html", tweet=tweet, user=tweet['user'])
            cls.since_ids[user['id']] = int(tweets[0]['id'])
            
            self.finish(chunk=text) # needs to come before we kill the poller            

            timeout = self.polls[user['id']]
            if timeout and self._finished and timeout in tornado.ioloop.IOLoop.instance()._timeouts:
                tornado.ioloop.IOLoop.instance().remove_timeout(timeout)
                cls.polls[user['id']] = None

class FacebookMixin(object):
    waiters = {}
    polls = {}
    since_ids = {}

    def get_current_user(self):
        return self.get_current_facebook_user()
        
    def poll_facebook(self):
        user = self.get_current_facebook_user()
        import time
        cls = FacebookMixin
        # since_id = cls.since_ids.get(user['uid'], 1)
        # print str(user['id']) + ' | since_id ' + str(since_id)
        timeout = self.polls.get(user['uid'], None)
        # Start polling if they havent already!
        if not timeout or timeout.deadline < time.time() and not self._finished:
            timeout = tornado.ioloop.IOLoop.instance().add_timeout(time.time() + POLL_INTERVAL, self.poll_facebook)
        self.polls[user['uid']] = timeout
        args = dict(method="stream.get",
                    session_key= user["session_key"],
                    callback = self.async_callback(self.write_stream))

        if cls.since_ids.get(user['uid'], None):
            args['start_time'] = cls.since_ids[user['uid']]
            print 'start_time: %d' % (args['start_time'])
        self.facebook_request(**args)
    
    def write_stream(self, stream):
        if stream is None:
            # Session may have expired
            self.redirect("/auth/login")
            #return

        if stream:
            cls = FacebookMixin
            user = self.get_current_facebook_user()
            posts = stream["posts"]
            if posts:
                text = self.get_text_from_stream(stream=stream)
                since_id = cls.since_ids.get(user['uid'], None)
                start_time = posts[0]['updated_time'] + 1
                if not since_id or start_time > since_id:
                    cls.since_ids[user['uid']]=start_time

                self.finish(chunk=text) # needs to come before we kill the poller
                
                timeout = self.polls[user['uid']]
                if timeout and self._finished and timeout in tornado.ioloop.IOLoop.instance()._timeouts:
                    tornado.ioloop.IOLoop.instance().remove_timeout(timeout)
                    self.polls[user['uid']] = None

    
    def get_text_from_stream(self, stream):
        text = ''
        stream["profiles"] = dict((p["id"], p) for p in stream["profiles"]) # mapping id => profile
        posts = stream["posts"]
        for post in posts:
            # print post
            # print "----------"
            try:
                text += self.render_string("modules/post.html", 
                                        post=post, 
                                        actor=stream["profiles"][post["actor_id"]])
            except:
                pass
        
        return text

class MainHandler(BaseHandler):
    def get(self):
        twitter_user = self.get_current_twitter_user()
        facebook_user =self.get_current_facebook_user()
        # print twitter_user
        # print facebook_user
        if twitter_user and TweetMixin.since_ids.get(twitter_user['id'], None):
            TweetMixin.since_ids.pop(twitter_user['id'])
        
        if facebook_user:
            if FacebookMixin.since_ids.get(facebook_user['uid'], None):
                FacebookMixin.since_ids.pop(facebook_user['uid'])

        self.render('index.html', 
                    twitter_user=twitter_user,
                    facebook_user=facebook_user)

class TwitterTimelineHandler(BaseHandler, TweetMixin, tornado.auth.TwitterMixin):
    # @tornado.web.authenticated
    @tornado.web.asynchronous
    def post(self):
        user = self.get_current_twitter_user()
        if user:
            self.async_callback(self.poll_twitter)()

class TwitterPreviousHandler(BaseHandler, TweetMixin, tornado.auth.TwitterMixin):
    # @tornado.web.authenticated
    @tornado.web.asynchronous 
    def post(self):
        user = self.get_current_twitter_user()
        if user:
            max_id = self.get_argument("max_id", None)
            if max_id:
                args = dict(path = "/statuses/friends_timeline",
                                     access_token=user["access_token"],
                                     max_id = int(max_id) - 1,
                                     callback = self.async_callback(self._on_post))
                self.twitter_request(**args)
    
    def _on_post(self, tweets):
        user = self.get_current_twitter_user()
        if user and tweets:
            text = ""
            for tweet in tweets:
                print tweet['id']
                text += self.render_string("modules/tweet.html", tweet=tweet, user=tweet['user'])        
            self.finish(text)

class TwitterStatusHandler(BaseHandler, TweetMixin, tornado.auth.TwitterMixin):
    # @tornado.web.authenticated
    @tornado.web.asynchronous 
    def post(self):
        user = self.get_current_twitter_user()
        if user:
            status = self.get_argument("status", None)
            if status:
                args = dict(path = "/statuses/update",
                             access_token=user["access_token"],
                             post_args={'status': status},
                             callback = self.async_callback(self._on_post))
                self.twitter_request(**args)
    
    def _on_post(self, status):
        text = ""
        user = self.get_current_twitter_user()
        if user and status:
            text += self.render_string("modules/tweet.html", tweet=status, user=status['user'])
        self.finish(text)
        
class TwitterStatusLastHandler(BaseHandler, TweetMixin, tornado.auth.TwitterMixin):
    # @tornado.web.authenticated
    @tornado.web.asynchronous 
    def post(self):
        user = self.get_current_twitter_user()
        if user:
            args = dict(path = "/statuses/user_timeline",
                         access_token=user["access_token"],
                         count=1,
                         callback = self.async_callback(self._on_post))
            self.twitter_request(**args)
    
    def _on_post(self, statuses):
        text = ""
        user = self.get_current_twitter_user()
        if user and statuses:
            text += self.render_string("modules/tweet.html", tweet=statuses[0], user=statuses[0]['user'])
        self.finish(text)
            
class FacebookStreamHandler(BaseHandler, FacebookMixin, tornado.auth.FacebookMixin):
    #@tornado.web.authenticated
    @tornado.web.asynchronous
    def post(self):
        user = self.get_current_facebook_user()
        if user:
            self.async_callback(self.poll_facebook)()

class FacebookPreviousHandler(BaseHandler, FacebookMixin, tornado.auth.FacebookMixin):
    #@tornado.web.authenticated
    @tornado.web.asynchronous
    def post(self):
        user = self.get_current_facebook_user()
        if user:
            end_time = self.get_argument("end_time", None)
            if end_time:
                end_time = int(end_time) - 1
                start_time = (end_time - (60 *  60 * 24) )
                
                # print "%d / %d" % (start_time, end_time)
                args = dict(method="stream.get",
                            session_key= user["session_key"],
                            start_time = start_time,
                            end_time = end_time,
                            callback = self.async_callback(self._on_post))
                self.facebook_request(**args)
    
    def _on_post(self, stream):
        user = self.get_current_facebook_user()
        if user and stream:
            text = ""
            posts = stream["posts"]
            if posts:
                text = self.get_text_from_stream(stream=stream)            
            self.finish(text)


class FacebookStatusHandler(BaseHandler, FacebookMixin, tornado.auth.FacebookMixin):
    #@tornado.web.authenticated
    @tornado.web.asynchronous
    def post(self):
        user = self.get_current_facebook_user()
        if user:
            status = self.get_argument("status", None)
            if status:
                args = dict(method="stream.publish",
                            session_key= user["session_key"],
                            uid=user['uid'],
                            message=status,
                            callback = self.async_callback(self._on_post))
                self.facebook_request(**args)

    def _on_post(self, status):
        user = self.get_current_facebook_user()
        self.finish("updated")

class FacebookStatusLastHandler(BaseHandler, FacebookMixin, tornado.auth.FacebookMixin):
    #@tornado.web.authenticated
    @tornado.web.asynchronous
    def post(self):
        user = self.get_current_facebook_user()
        if user:
            args = dict(method="status.get",
                        session_key= user["session_key"],
                        uid=user['uid'],
                        limit=1,
                        callback = self.async_callback(self._on_post))
            self.facebook_request(**args)
            
    def _on_post(self, status):
        text = ""
        user = self.get_current_facebook_user()
        print status
        if user and status:
            if len(status) > 0:
                #[{u'source': 10732101402L, u'message': u'Our first post w @pingfm. 
                # Yep @MerchantCircle has just been added to ping.fm start updating MC w all of your other fav social networks',
                # u'status_id': 143652407725L, u'uid': 1562261327, u'time': 1254184501}]
                post = status[0]
                post['created_time'] = post.get('time')
                user['url'] = user.get('profile_url')
                text += self.render_string("modules/post.html", 
                                        post=post,
                                        actor=user)
                
        self.finish(text)

class AuthTwitterHandler(BaseHandler, tornado.auth.TwitterMixin):
    @tornado.web.asynchronous
    def get(self):
        if self.get_argument("oauth_token", None):
            self.get_authenticated_user(self.async_callback(self._on_auth))
            return
        self.authorize_redirect()

    def _on_auth(self, user):
        if not user:
            raise tornado.web.HTTPError(500, "Twitter auth failed")
        self.save_current_twitter_user(user)
        self.xsrf_token
        self.redirect("/")

class AuthFacebookHandler(BaseHandler, tornado.auth.FacebookMixin):
    @tornado.web.asynchronous
    def get(self):
        if self.get_argument("session", None):
            self.get_authenticated_user(self.async_callback(self._on_auth))
            return
        self.authorize_redirect("read_stream,publish_stream")
    
    def _on_auth(self, user):
        if not user:
            raise tornado.web.HTTPError(500, "Facebook auth failed")
        self.save_current_facebook_user(user)
        self.xsrf_token
        self.redirect(self.get_argument("next", "/"))

class AuthLogoutHandler(BaseHandler, tornado.auth.FacebookMixin):
    def get(self):
        logout = self.get_argument('logout', None)
        twitter_user = self.get_current_twitter_user()
        facebook_user = self.get_current_facebook_user()
        if logout == 'twitter':
            self.clear_cookie("twitter_user")
            twitter_user = None
        if logout == 'facebook':        
            self.clear_cookie("facebook_user")
            facebook_user = None
        if not twitter_user and not facebook_user:
            self.clear_cookie("_xsrf")
        self.redirect(self.get_argument("next", "/"))

class TweetModule(tornado.web.UIModule):
    def render(self, tweet, user=None):
        return self.render_string("modules/tweet.html", tweet=tweet, user=user)

class PostModule(tornado.web.UIModule):
    def render(self, post):
        return self.render_string("modules/post.html", post=post)

def main():
    tornado.options.parse_command_line()
    http_server = tornado.httpserver.HTTPServer(Application())
    http_server.listen(options.port)
    tornado.ioloop.IOLoop.instance().start()
    # tornado.autoreload.start()
    
if __name__ == "__main__":
    main()
