# TweetMirrorBot
A Reddit bot that mirrors images from tweets.

###Prerequisites: 
 - API keys and tokens for reddit, twitter and imgur
 - Redis database

###Local Usage: 
 - Install requirements with `pip install -r requirements.txt`
 - Set environmental veriables in a `.env` file

    > REDISTOGO_URL="REDIS://localhost:6379"
    > 
    > REDDIT_CLIENT_ID=""
    > REDDIT_CLIENT_SECRET=""
    > REDDIT_PASSWORD=""
    > REDDIT_REDIRECT_URL=""
    > REDDIT_USER_AGENT=""
    > REDDIT_USER_NAME=""
    > 
    > TWITTER_CONSUMER_KEY=""
    > TWITTER_CONSUMER_SECRET=""
    > TWITTER_ACCESS_TOKEN_KEY="" 
    > TWITTER_ACCESS_TOKEN_SECRET=""
    > 
    > IMGUR_CLIENT_ID=""
    
 - Run `heroku local -f Procfile`

###Deploying to Heroku: 
 - Follow the instructions [here](https://devcenter.heroku.com/articles/git)
 - Add add-on `Redis To Go` and `Heroku Scheduler`
 - Create a scheduled job in `Heroku Scheduler`