#!/home/jonnosan/fed_watch/.venv/bin/python3

import logging
import argparse
import fed_watch
import os
import requests
import requests_cache

from typing import List, Dict
from atproto import Client
from PIL import Image
from io import BytesIO

LOGO_URL = 'https://encrypted-tbn0.gstatic.com/images?q=tbn:ANd9GcTiiHSpB0njJL_2liJLC_Wae1YEriG44DGjxfMo33Yyq7-ajVaB2TuoeVYe-Q0s2ZBCQ44&usqp=CAU'

#"https://www.fedcourt.gov.au/__data/assets/image/0009/19908/logo.png"

# Download the logo and store as a binary blob
try:
    logo_session = requests_cache.CachedSession('logo_cache',cache_control=False)

    response = logo_session.get(LOGO_URL)
    response.raise_for_status()
    LOGO_BLOB = response.content
except Exception as e:
    LOGO_BLOB = None
    print(f"Failed to download logo: {e}")
    system.exit(-1) 
import re
#given a string, return a list  of locations of all URLs in that string
def parse_urls(text: str) -> List[Dict]:
    spans = []
    # partial/naive URL regex based on: https://stackoverflow.com/a/3809435
    # tweaked to disallow some training punctuation
    url_regex = rb"[$|\W](https?:\/\/(www\.)?[-a-zA-Z0-9@:%._\+~#=]{1,256}\.[a-zA-Z0-9()]{1,6}\b([-a-zA-Z0-9()@:%_\+.~#?&//=]*[-a-zA-Z0-9@%_\+~#//=])?)"
    text_bytes = text.encode("UTF-8")
    for m in re.finditer(url_regex, text_bytes):
        spans.append({
            "start": m.start(1),
            "end": m.end(1),
            "url": m.group(1).decode("UTF-8"),
        })
    return spans


def parse_facets(text: str) -> List[Dict]:
    facets = []
    for u in parse_urls(text):
        facets.append({
            "index": {
                "byteStart": u["start"],
                "byteEnd": u["end"],
            },
            "features": [
                {
                    "$type": "app.bsky.richtext.facet#link",
                    # NOTE: URI ("I") not URL ("L")
                    "uri": u["url"],
                }
            ],
        })
    return facets

#delete any prior posts that contain the specified target string
def delete_all_prior_posts(client,logger):
    data = client.get_author_feed(
        actor=client.me.did,
        filter='posts_no_replies,',
        limit=100,
    )
    
    feed = data.feed
    for feeditem in feed:
        post=feeditem.post
        logger.info(f'purge requested - deleting {post.uri}')
        client.delete_post(post.uri)

def find_prior_posts(client,logger,target_string):
    data = client.get_author_feed(
        actor=client.me.did,
        filter='posts_no_replies,',
        limit=100,
    )
    
    feed = data.feed
    for feeditem in feed:
        post=feeditem.post
        post_text=post.record.text
        if (post_text.find(target_string)>=0):
            logger.info(f"found {target_string} in {post.uri}")
            return(post)    
        else:
            logger.debug(f"{target_string} not in {post_text} {post.uri} - ignoring!")            
    return(None)    


def make_case_post(client,logger,case_url,case_name,most_recent_date,updated_docs):
    from urllib.parse import urlparse
    case_id=urlparse(case_url).path.rstrip('/').split('/')[-1]
    post_id= f"{case_id}::{most_recent_date.strftime('%Y-%m-%d')}"
    logger.info(f"{post_id} - {case_name}: {case_url} - updated on {most_recent_date.strftime('%d %B %Y')}")

    prior_post=find_prior_posts(client,logger,post_id)
    if prior_post is not None:
        logger.info(f"Found {post_id} at {prior_post.uri} - new post not needed")
        return(prior_post)

    logger.info(f"no post found with {post_id} - new post needed")


    text=f"Online Court File for '{case_name}' was updated on {most_recent_date.strftime('%d %B %Y')}\n\n{post_id}"

    from atproto import models
    thumb = client.upload_blob(LOGO_BLOB)
    embed = models.AppBskyEmbedExternal.Main(
        external=models.AppBskyEmbedExternal.External(
            title=f'Federal Court of Australia \n{case_name}',
            description=text,
            uri=case_url,
            thumb=thumb.blob,

        )
    )

    root_post = client.send_post(text,  facets=parse_facets(text), embed=embed)
   
    logger.info(f"Posted: {root_post.uri} ")

    root = models.create_strong_ref(root_post)
    parent=root
    #now add posts for each document
    for doc_name, doc_url, doc_date in updated_docs:
        if doc_url and not doc_url.startswith('http'):
            doc_url = f"https://www.fedcourt.gov.au{doc_url}"
        logger.info(f"  {doc_name}: {doc_url if doc_url else ''} (Published: {doc_date.strftime('%d %B %Y')})")
        text=f"{doc_name} was published on {doc_date.strftime('%d %B %Y')}\n\n{doc_url}"
        post = client.send_post(text, facets=parse_facets(text),reply_to=models.AppBskyFeedPost.ReplyRef(parent=parent, root=root))
        logger.info(f"Document posted: {post.uri}")
        parent = models.create_strong_ref(post)
    return(root_post) 

    for doc_name, doc_url, doc_date in updated_docs:
        if doc_url and not doc_url.startswith('http'):
            doc_url = f"https://www.fedcourt.gov.au{doc_url}"
        logger.info(f"  {doc_name}: {doc_url if doc_url else ''} (Published: {doc_date.strftime('%d %B %Y')})")

 

def main():
    parser = argparse.ArgumentParser(description="Bot that uses fed_watch functions.")
    parser.add_argument('-v','--verbose', action='store_true', help='Enable verbose output')
    parser.add_argument('--debug', action='store_true', help='Enable debug output')
    parser.add_argument('--days', type=int, default=2, help='How many days back to check for new links (default: 2)')
    parser.add_argument("--purge-all-posts", help="deletes all prior posts on account",action="store_true")

    args = parser.parse_args()

    log_level = logging.DEBUG if args.debug else logging.INFO if args.verbose else logging.ERROR
    logging.basicConfig(level=log_level, format='%(message)s')
    logger = logging.getLogger("bsky_bot")
    logger.info("setting log level to %s", logging.getLevelName(log_level))


    if ('FEDWATCH_USER' not in os.environ):
        print("FEDWATCH_USER env variable not found")
        exit(-1)

    if ('FEDWATCH_PASS' not in os.environ):
        print("FEDWATCH_PASS env variable not found")
        exit(-1)

    bsky_user=os.environ['FEDWATCH_USER']
    bsky_pass=os.environ['FEDWATCH_PASS']
    logger.info(f"logging in as {bsky_user}:{"*"*len(bsky_pass)}") 
    client = Client()
    client.login(bsky_user, bsky_pass)


    if args.purge_all_posts:
        logger.info(f'*** PURGING ALL PRIOR POSTS ***')
        delete_all_prior_posts(client,logger)


    # Example: get all open files links
    links = fed_watch.get_open_files_links(logger)
    logger.debug(f"Found {len(links)} open files links.")


    for name, href in links:
        url = href if href.startswith("http") else f"https://www.fedcourt.gov.au{href}"
        most_recent_date,recently_updated_docs=fed_watch.get_recently_updated_docs(url, logger, args.days)
        if recently_updated_docs and len(recently_updated_docs) > 0:
            make_case_post(client,logger,url,name,most_recent_date,recently_updated_docs)

if __name__ == "__main__":
    main()
