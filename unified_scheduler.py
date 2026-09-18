# -*- coding: utf-8 -*-
"""
統合 SNS 投稿・運用ボット (Bluesky)
- posts.csv からの自動投稿 (Bluesky)
- Bluesky 積極的獲得機能 (いいね、フォロバ、関連ユーザーフォロー)
"""

import csv
import time
import os
import re
import json
import random
import requests
from datetime import datetime, timezone, timedelta
from atproto import Client, client_utils, models
from dotenv import load_dotenv

# --- 設定 ---
if os.path.exists(".env"):
    load_dotenv(encoding="utf-8")

# Bluesky 設定
BLUESKY_HANDLE = os.getenv("BLUESKY_HANDLE")
BLUESKY_PASSWORD = os.getenv("BLUESKY_PASSWORD")
POSTED_FLAG_BSKY = "posted"



# 共通設定
POSTS_CSV_PATH = os.path.join(os.path.dirname(__file__), "posts.csv")
JST = timezone(timedelta(hours=9))

# --- 積極的獲得機能の設定（運用テーマに合わせて自由に変更してください） ---
KEYWORDS = ["AI活用", "ChatGPT", "業務効率化", "生成AI", "プロンプト"]
PROACTIVE_INTERVAL = 18000  # 5時間 (秒単位)
HASHTAG_POOL = ["#AI", "#ChatGPT", "#業務効率化", "#AI活用", "#生成AI", "#時短術", "#副業"]
# 投稿を積極的にいいね/リポストしたい特定アカウント（任意・空文字なら無効）
TARGET_ACCOUNT = os.getenv("BLUESKY_TARGET_ACCOUNT", "")

# アフィリエイト設定
ENABLE_AFFILIATE = True
AFFILIATE_LIST_FILE = os.path.join(os.path.dirname(__file__), "affiliate_posts.json")
# 毎日以下の時刻にランダムで1回投稿する
AFFILIATE_SCHEDULED_TIMES = ["12:00", "19:00"]
# 投稿済みの状態を記録するファイル
AFFILIATE_POSTED_LOG = os.path.join(os.path.dirname(__file__), "affiliate_posted.json")
# 画像付きアフィリエイト投稿でリンクカードのタイトル/説明が未指定の場合のデフォルト値
DEFAULT_AFFILIATE_TITLE = os.getenv("DEFAULT_AFFILIATE_TITLE", "おすすめサービス")
DEFAULT_AFFILIATE_DESC = os.getenv("DEFAULT_AFFILIATE_DESC", "詳しくはリンク先をご覧ください")
DEFAULT_AFFILIATE_URL = os.getenv("DEFAULT_AFFILIATE_URL", "")

def load_affiliate_posts():
    if not os.path.exists(AFFILIATE_LIST_FILE):
        return []
    try:
        with open(AFFILIATE_LIST_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"⚠️ アフィリエイトリストの読み込みエラー: {e}")
        return []

def load_affiliate_log():
    if not os.path.exists(AFFILIATE_POSTED_LOG):
        return {}
    try:
        with open(AFFILIATE_POSTED_LOG, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return {}

def save_affiliate_log(log_data):
    try:
        with open(AFFILIATE_POSTED_LOG, "w", encoding="utf-8") as f:
            json.dump(log_data, f, ensure_ascii=False, indent=4)
    except Exception as e:
        print(f"⚠️ アフィリエイトログ保存エラー: {e}")

def is_japanese_user(post):
    """ユーザーが日本語を使用しているか判定する"""
    # 1. 投稿の言語メタデータをチェック
    if hasattr(post, 'record') and hasattr(post.record, 'langs'):
        if post.record.langs and 'ja' in post.record.langs:
            return True
    
    # 2. 投稿本文またはプロフィールに日本語（ひらがな・カタカナ）が含まれているかチェック
    # (メタデータがない場合の補助判定)
    text_to_check = ""
    if hasattr(post, 'record') and hasattr(post.record, 'text'):
        text_to_check += post.record.text
    if hasattr(post.author, 'description') and post.author.description:
        text_to_check += post.author.description
    
    if re.search(r'[\u3040-\u309F\u30A0-\u30FF]', text_to_check):
        return True
        
    return False

def load_posts(csv_path):
    posts = []
    if not os.path.exists(csv_path):
        print(f"❌ ファイルが見つかりません: {csv_path}")
        return []
    try:
        with open(csv_path, encoding="utf-8-sig", newline="") as f:
            valid_lines = [line for line in f if line.strip() and not line.strip().startswith("#")]
            if not valid_lines: return []
            reader = csv.DictReader(valid_lines)
            for row in reader: posts.append(row)
    except Exception as e:
        print(f"❌ CSV読み込みエラー: {e}")
    return posts

def save_posts(csv_path, posts):
    if not posts: return
    fieldnames = list(posts[0].keys())
    if POSTED_FLAG_BSKY not in fieldnames: fieldnames.append(POSTED_FLAG_BSKY)
    try:
        with open(csv_path, "w", encoding="utf-8-sig", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(posts)
    except Exception as e:
        print(f"❌ CSV保存エラー: {e}")

def fetch_ogp_data(url):
    """URLからOGP情報(title, description, image data)を取得する"""
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
        resp = requests.get(url, headers=headers, timeout=10)
        resp.raise_for_status()
        html = resp.text

        og_title = ""
        m_title = re.search(r'property="og:title"\s+content="([^"]+)"', html) or re.search(r'content="([^"]+)"\s+property="og:title"', html)
        if m_title: og_title = m_title.group(1)
        else:
            m_title = re.search(r'<title>(.*?)</title>', html, re.IGNORECASE)
            if m_title: og_title = m_title.group(1)
            
        og_desc = ""
        m_desc = re.search(r'property="og:description"\s+content="([^"]+)"', html) or re.search(r'content="([^"]+)"\s+property="og:description"', html)
        if m_desc: og_desc = m_desc.group(1)

        og_image = ""
        m_img = re.search(r'property="og:image"\s+content="([^"]+)"', html) or re.search(r'content="([^"]+)"\s+property="og:image"', html)
        if m_img: og_image = m_img.group(1)

        img_data = None
        if og_image:
            og_image = og_image.replace("&amp;", "&")
            img_resp = requests.get(og_image, headers=headers, timeout=10)
            if img_resp.status_code == 200:
                img_data = img_resp.content

        return og_title, og_desc, img_data
    except Exception as e:
        print(f"OGP取得エラー ({url}): {e}")
        return "", "", None

def post_to_bluesky(client, text, image_path=None, card_title=None, card_desc=None):
    try:
        # 既存のハッシュタグ（#または＃で始まるもの）を削除
        text_without_tags = re.sub(r'[#\uff03][^\s]+', '', text).strip()
        
        # ランダムにハッシュタグを1つ選択して追加
        chosen_tag = random.choice(HASHTAG_POOL)
        final_text = f"{text_without_tags}\n\n{chosen_tag}"

        # URLとハッシュタグをパースしてTextBuilderを構築
        tb = client_utils.TextBuilder()
        pattern = r'(https?://[^\s]+|[#\uff03][A-Za-z0-9_\u3041-\u3096\u30a1-\u30fa\u4e00-\u9faf]+)'
        last_idx = 0
        urls = []
        for m in re.finditer(pattern, final_text):
            tb.text(final_text[last_idx:m.start()])
            match_str = m.group(1)
            if match_str.startswith('http'):
                tb.link(match_str, match_str)
                urls.append(match_str)
            else:
                tag_name = match_str[1:] 
                tb.tag(match_str, tag_name)
            last_idx = m.end()
        tb.text(final_text[last_idx:])
        
        embed = None
        target_url = urls[0] if urls else None

        # OGP取得用の変数
        final_title = card_title
        final_desc = card_desc
        img_data = None

        if image_path and os.path.exists(image_path):
            # ローカル画像が指定された場合
            with open(image_path, 'rb') as f:
                img_data = f.read()
            if not target_url:
                target_url = DEFAULT_AFFILIATE_URL
            final_title = final_title if final_title else DEFAULT_AFFILIATE_TITLE
            final_desc = final_desc if final_desc else DEFAULT_AFFILIATE_DESC
        elif target_url:
            # 画像がない場合はURLからOGP情報を自動取得
            print(f"URLからOGP情報を取得中... ({target_url})")
            og_title, og_desc, og_img_data = fetch_ogp_data(target_url)
            
            if og_img_data:
                img_data = og_img_data
            if not final_title and og_title:
                final_title = og_title
            if not final_desc and og_desc:
                final_desc = og_desc

        if img_data and target_url:
            blob_resp = client.upload_blob(img_data)
            embed = models.AppBskyEmbedExternal.Main(
                external=models.AppBskyEmbedExternal.External(
                    title=final_title or "",
                    description=final_desc or "",
                    uri=target_url,
                    thumb=blob_resp.blob,
                )
            )

        if embed:
            client.send_post(text=tb, embed=embed)
            print(f"Bluesky リンクカード付き投稿成功: {final_text[:30]}...")
        else:
            if image_path:
                print(f"⚠️ 画像ファイルが見つかりません: {image_path} (テキストのみ投稿します)")
            client.send_post(text=tb)
            print(f"Bluesky テキスト投稿成功: {final_text[:30]}...")
            
        return True
    except Exception as e:
        print(f"Bluesky 投稿エラー: {e}")
        return False


# --- Proactive Bot Functions ---

def run_proactive_actions(client: Client):
    """Blueskyの積極的獲得アクション（いいね・フォロー・フォロバ）を実行"""
    print(f"\n[{datetime.now(JST).strftime('%H:%M:%S')}] Bluesky 運用アクションを開始します...")
    
    # 1. 自動フォロバ
    print("フォロワーを確認中...")
    try:
        profile = client.get_profile(actor=BLUESKY_HANDLE)
        my_did = profile.did
        
        # フォロワーを全件取得
        followers = []
        cursor = None
        while True:
            params = {'actor': my_did, 'limit': 100}
            if cursor:
                params['cursor'] = cursor
            res = client.app.bsky.graph.get_followers(params=params)
            followers.extend(res.followers)
            if not getattr(res, 'cursor', None):
                break
            cursor = res.cursor
            
        # フォロー中を全件取得
        following_dids = set()
        cursor = None
        while True:
            params = {'actor': my_did, 'limit': 100}
            if cursor:
                params['cursor'] = cursor
            res = client.app.bsky.graph.get_follows(params=params)
            for f in res.follows:
                following_dids.add(f.did)
            if not getattr(res, 'cursor', None):
                break
            cursor = res.cursor
        
        fb_count = 0
        for follower in followers:
            if follower.did not in following_dids:
                client.follow(follower.did)
                fb_count += 1
                time.sleep(2)
        if fb_count > 0: print(f"フォローバックを {fb_count}件完了。")
        else: print("新しくフォローバックする相手はいませんでした。")
    except Exception as e:
        import traceback
        print(f"フォロバ中にエラー: {e}")
        traceback.print_exc()

    # 2. キーワード検索による「いいね」と「フォロー」の候補収集
    all_posts = []
    for kw in KEYWORDS:
        try:
            search_results = client.app.bsky.feed.search_posts(params={'q': kw, 'limit': 10})
            all_posts.extend(search_results.posts)
        except Exception as e: print(f"「{kw}」の検索中にエラー: {e}")

    if not all_posts:
        print("検索結果が見つかりませんでした。")
        return

    # 3. ランダムいいね (3件)
    print("ランダムにいいねを送信中...")
    like_count = 0
    target_posts = random.sample(all_posts, min(len(all_posts), 10)) # 候補を絞る
    for post in target_posts:
        if like_count >= 3: break
        try:
            client.like(post.uri, post.cid)
            like_count += 1
            print(f"いいね成功: @{post.author.handle}")
            time.sleep(3)
        except: continue
    print(f"{like_count}件にいいねしました。")

    # 4. 関連ユーザーの自動フォロー (5件)
    print("関連ユーザーを探索・フォロー中...")
    try:
        follow_count = 0
        profile = client.get_profile(actor=BLUESKY_HANDLE)
        
        following_dids = set()
        cursor = None
        while True:
            params = {'actor': profile.did, 'limit': 100}
            if cursor:
                params['cursor'] = cursor
            res = client.app.bsky.graph.get_follows(params=params)
            for f in res.follows:
                following_dids.add(f.did)
            if not getattr(res, 'cursor', None):
                break
            cursor = res.cursor

        for post in all_posts:
            if follow_count >= 5: break
            author_did = post.author.did
            
            # 日本語アカウントかつ未フォローの場合のみフォロー
            if author_did != profile.did and author_did not in following_dids:
                if is_japanese_user(post):
                    try:
                        client.follow(author_did)
                        following_dids.add(author_did)
                        follow_count += 1
                        print(f"新規フォロー (JA): @{post.author.handle}")
                        time.sleep(5)
                    except: continue
                else:
                    # 日本語以外はスキップ
                    pass
        print(f"合計 {follow_count}人の新規ユーザーをフォローしました。")
    except Exception as e:
        import traceback
        print(f"関連ユーザーフォロー中にエラー: {e}")
        traceback.print_exc()

    # 5. 特定アカウントの投稿をリポスト＆いいね（BLUESKY_TARGET_ACCOUNT が未設定ならスキップ）
    if TARGET_ACCOUNT:
        print(f"特定アカウント (@{TARGET_ACCOUNT}) の最新投稿をチェック中...")
        try:
            author_feed = client.app.bsky.feed.get_author_feed(params={'actor': TARGET_ACCOUNT, 'limit': 1})
            action_count = 0
            for item in author_feed.feed:
                post = item.post
                viewer = getattr(post, 'viewer', None)

                # いいね
                if not viewer or not getattr(viewer, 'like', None):
                    try:
                        client.like(post.uri, post.cid)
                        print(f"特定アカウントいいね成功: {post.uri.split('/')[-1]}")
                        action_count += 1
                        time.sleep(2)
                    except Exception as e:
                        pass

                # リポスト
                if not viewer or not getattr(viewer, 'repost', None):
                    try:
                        client.repost(post.uri, post.cid)
                        print(f"特定アカウントリポスト成功: {post.uri.split('/')[-1]}")
                        action_count += 1
                        time.sleep(2)
                    except Exception as e:
                        pass

            if action_count == 0:
                print(f"@{TARGET_ACCOUNT} の新しい投稿（未いいね・未リポスト）はありませんでした。")
        except Exception as e:
            print(f"特定アカウント (@{TARGET_ACCOUNT}) のチェック中にエラー: {e}")

    print("運用アクション完了。\n")

def main():
    print("統合 SNS スケジューラー＆ボット起動")
    
    bsky_enabled = bool(BLUESKY_HANDLE and BLUESKY_PASSWORD)
    
    if not bsky_enabled:
        print("❌ 設定情報が不足しています。")
        return

    bsky_client = None
    if bsky_enabled:
        try:
            bsky_client = Client()
            bsky_client.login(BLUESKY_HANDLE, BLUESKY_PASSWORD)
            print(f"✅ Bluesky ログイン成功 (@{BLUESKY_HANDLE})")
        except Exception as e:
            import traceback
            print(f"⚠️ Bluesky ログインエラー (一時的な通信エラー等): {e}")
            traceback.print_exc()
            print("💡 プログラムは続行し、5分おきのチェック時に自動で再接続を試みます。")
            bsky_client = None

    last_proactive_run = 0 # 初回起動時に実行するように設定
    affiliate_log = load_affiliate_log()

    while True:
        now_jst = datetime.now(JST)
        current_time_ts = time.time()
        
        # --- Bluesky 未接続時の再接続処理 ---
        if bsky_enabled and bsky_client is None:
            try:
                bsky_client = Client()
                bsky_client.login(BLUESKY_HANDLE, BLUESKY_PASSWORD)
                print(f"✅ Bluesky ログイン復帰成功 (@{BLUESKY_HANDLE})")
            except Exception as e:
                import traceback
                print(f"⚠️ Bluesky ログイン再試行エラー (5分後にまた試みます): {e}")
                traceback.print_exc()
                bsky_client = None

        # 1. 積極的獲得機能のチェック (3時間おき)
        if bsky_client is not None and (current_time_ts - last_proactive_run >= PROACTIVE_INTERVAL):
            run_proactive_actions(bsky_client)
            last_proactive_run = current_time_ts

        # 1.5 アフィリエイト投稿のチェック (指定時間ランダム)
        if ENABLE_AFFILIATE and bsky_client is not None:
            today_str = now_jst.strftime('%Y-%m-%d')
            for scheduled_time in AFFILIATE_SCHEDULED_TIMES:
                try:
                    target_dt = datetime.strptime(f"{today_str} {scheduled_time}", "%Y-%m-%d %H:%M").replace(tzinfo=JST)
                except ValueError:
                    continue
                
                log_key = f"{today_str}_{scheduled_time}"
                
                if now_jst >= target_dt and log_key not in affiliate_log:
                    aff_posts = load_affiliate_posts()
                    if aff_posts:
                        post_data = random.choice(aff_posts)
                        content = post_data.get("text", "")
                        
                        raw_image_path = post_data.get("image")
                        image_path = None
                        if raw_image_path:
                            image_path = raw_image_path if os.path.isabs(raw_image_path) else os.path.join(os.path.dirname(__file__), raw_image_path)
                            
                        card_title = post_data.get("title")
                        card_desc = post_data.get("desc")
                        
                        print(f"\n[{now_jst.strftime('%H:%M:%S')}] アフィリエイト投稿(ランダム)を実行します: {scheduled_time}")
                        if post_to_bluesky(bsky_client, content, image_path, card_title, card_desc):
                            affiliate_log[log_key] = True
                            save_affiliate_log(affiliate_log)
                        else:
                            print("⚠️ アフィリエイト投稿に失敗しました。次回リトライします。")
                    break

        # 2. 投稿スケジュールのチェック (1分おき)
        posts = load_posts(POSTS_CSV_PATH)
        if posts:
            updated = False
            remaining_bsky = 0
            
            for post in posts:
                scheduled_str = post.get("scheduled_datetime", "").strip()
                content = post.get("content", "").strip()
                image_path = post.get("image_path", "").strip()
                if not image_path: image_path = None
                
                if not scheduled_str or not content: continue
                
                try:
                    scheduled_dt = datetime.fromisoformat(scheduled_str).replace(tzinfo=JST)
                except ValueError: continue

                if now_jst >= scheduled_dt:
                    if bsky_client is not None and post.get(POSTED_FLAG_BSKY) != "true":
                        if post_to_bluesky(bsky_client, content, image_path):
                            post[POSTED_FLAG_BSKY] = "true"
                            updated = True
                
                if bsky_enabled and post.get(POSTED_FLAG_BSKY) != "true": remaining_bsky += 1
            
            if updated: save_posts(POSTS_CSV_PATH, posts)
            
            # 全体終了チェック（投稿のみ）
            is_all_posted_bsky = not bsky_enabled or not any(p.get(POSTED_FLAG_BSKY) != "true" for p in posts)
            
            if is_all_posted_bsky and remaining_bsky == 0 and len(posts) > 0:
                print(f"♻️ [{now_jst.strftime('%H:%M:%S')}] すべての予約投稿が完了しました。新しいスケジュールを自動生成します...")
                try:
                    import subprocess
                    subprocess.run(["python", "update_posts.py"], cwd=os.path.dirname(__file__), check=True)
                    print("✅ 新しいスケジュールの生成が完了しました！次回のチェックから新しいスケジュールが開始されます。")
                    continue
                except Exception as e:
                    print(f"⚠️ スケジュール自動生成に失敗しました: {e}")

            status_msg = f"🕒 [{now_jst.strftime('%H:%M:%S')}] 待機中... (残り Bsky投稿:{remaining_bsky})"
            # 運用機能の次回の実行までの時間も表示
            next_proactive = int(PROACTIVE_INTERVAL - (current_time_ts - last_proactive_run))
            if next_proactive < 0:
                next_proactive = 0
            if bsky_enabled:
                status_msg += f" | 次の運用: {next_proactive // 60}分"
            print(status_msg)

        time.sleep(300) # 5分おきにチェック

if __name__ == "__main__":
    main()
