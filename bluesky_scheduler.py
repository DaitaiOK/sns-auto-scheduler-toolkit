# -*- coding: utf-8 -*-
import csv
import time
import os
import sys
import re
from datetime import datetime, timezone, timedelta
from atproto import Client, client_utils
from dotenv import load_dotenv

# --- Settings ---
if os.path.exists(".env"):
    load_dotenv(encoding="utf-8")

BLUESKY_HANDLE = os.getenv("BLUESKY_HANDLE")
BLUESKY_PASSWORD = os.getenv("BLUESKY_PASSWORD")
POSTS_CSV_PATH = os.path.join(os.path.dirname(__file__), "posts.csv")
JST = timezone(timedelta(hours=9))
POSTED_FLAG = "posted"

def load_posts(csv_path):
    posts = []
    if not os.path.exists(csv_path):
        print(f"File not found: {csv_path}")
        return []
    try:
        with open(csv_path, encoding="utf-8-sig", newline="") as f:
            valid_lines = [line for line in f if line.strip() and not line.strip().startswith("#")]
            if not valid_lines: return []
            reader = csv.DictReader(valid_lines)
            for row in reader: posts.append(row)
    except Exception as e:
        print(f"CSV Load Error: {e}")
    return posts

def save_posts(csv_path, posts):
    if not posts: return
    fieldnames = list(posts[0].keys())
    if POSTED_FLAG not in fieldnames: fieldnames.append(POSTED_FLAG)
    try:
        with open(csv_path, "w", encoding="utf-8-sig", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(posts)
    except Exception as e:
        print(f"CSV Save Error: {e}")

def post_to_bluesky(client, text):
    """Post to Bluesky with clickable hashtags using facets."""
    try:
        tb = client_utils.TextBuilder()
        
        # More robust hashtag matching
        # Matches #tag or ＃tag preceded by start of string or whitespace
        # Tag name can include alphanumeric, underscore, and Japanese characters
        pattern = r'([#\uff03][A-Za-z0-9_\u3041-\u3096\u30a1-\u30fa\u4e00-\u9faf]+)'
        
        last_idx = 0
        has_tags = False
        for m in re.finditer(pattern, text):
            # Append text before tag
            tb.text(text[last_idx:m.start()])
            
            # Append tag as a facet
            tag_text = m.group(1)
            tag_name = tag_text[1:] # Tag name without #
            tb.tag(tag_text, tag_name)
            
            last_idx = m.end()
            has_tags = True
        
        # Append remaining text
        tb.text(text[last_idx:])
        
        # Send post using the TextBuilder object (explicitly)
        client.send_post(text=tb)
        
        print(f"Success: {text[:30]}... (Hashtags linked)")
        return True
    except Exception as e:
        print(f"Post Error: {e}")
        return False

def main():
    if not BLUESKY_HANDLE or not BLUESKY_PASSWORD:
        print("Env error: BLUESKY_HANDLE or BLUESKY_PASSWORD not set.")
        return
    print(f"Starting Bluesky Scheduler for @{BLUESKY_HANDLE}...")
    client = Client()
    try:
        client.login(BLUESKY_HANDLE, BLUESKY_PASSWORD)
        print("Login successful.")
    except Exception as e:
        print(f"Login Error: {e}")
        return
    
    while True:
        now_jst = datetime.now(JST)
        posts = load_posts(POSTS_CSV_PATH)
        if not posts: 
            print("No more posts in CSV.")
            break
            
        posted_any = False
        remaining_count = 0
        
        for post in posts:
            if post.get(POSTED_FLAG) == "true": continue
            
            scheduled_str = post.get("scheduled_datetime", "").strip()
            content = post.get("content", "").strip()
            if not scheduled_str or not content: continue
            
            try:
                scheduled_dt = datetime.fromisoformat(scheduled_str).replace(tzinfo=JST)
            except ValueError: continue
            
            if now_jst >= scheduled_dt:
                if post_to_bluesky(client, content):
                    post[POSTED_FLAG] = "true"
                    posted_any = True
            else:
                remaining_count += 1
        
        if posted_any:
            save_posts(POSTS_CSV_PATH, posts)
            
        if not any(p.get(POSTED_FLAG) != "true" for p in posts):
            print("All scheduled posts completed!")
            break
            
        print(f"[{now_jst.strftime('%H:%M:%S')}] Waiting... ({remaining_count} posts remaining)")
        time.sleep(60)

if __name__ == "__main__":
    main()
