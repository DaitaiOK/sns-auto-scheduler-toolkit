"""
Bluesky 積極的獲得ボット (Proactive Engagement Bot)

機能:
  1. 自動フォロバ: 自分をフォローしてくれている人を自動でフォローバックします。
  2. 自動いいね: 指定したキーワード（AI, ChatGPTなど）を検索し、最新の投稿にいいねをします。

注意:
  短時間に大量のアクションを行うと、アカウントがスパム判定されるリスクがあります。
  このスクリプトは安全な頻度（1時間に数回など）で実行することを推奨します。
"""

import os
import time
from atproto import Client
from dotenv import load_dotenv

# .envファイルから認証情報を読み込み
load_dotenv(encoding="utf-8")

BLUESKY_HANDLE = os.getenv("BLUESKY_HANDLE")
BLUESKY_PASSWORD = os.getenv("BLUESKY_PASSWORD")

# ターゲットキーワード
KEYWORDS = ["AI活用", "ChatGPT", "業務効率化", "生成AI", "プロンプト"]

def follow_back(client: Client):
    """自分をフォローしているが、自分はフォローしていない人をフォローバックする"""
    print("🔍 フォロワーを確認中...")
    try:
        # 自分の情報を取得
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
        
        count = 0
        for follower in followers:
            if follower.did not in following_dids:
                print(f"👤 フォローバックします: @{follower.handle}")
                client.follow(follower.did)
                count += 1
                time.sleep(2) # スパム防止の待機
        
        if count > 0:
            print(f"✅ {count}件のフォローバックを完了しました。")
        else:
            print("✨ 新しくフォローバックする相手はいませんでした。")
            
    except Exception as e:
        import traceback
        print(f"❌ フォロバ中にエラーが発生: {e}")
        traceback.print_exc()

def like_by_keywords(client: Client):
    """キーワードで検索し、最新の投稿にいいねをする"""
    print(f"🔍 キーワード検索で「いいね」を送信中... {KEYWORDS}")
    
    for kw in KEYWORDS:
        try:
            # キーワードで投稿を検索
            search_results = client.app.bsky.feed.search_posts(params={'q': kw, 'limit': 5})
            
            count = 0
            for post in search_results.posts:
                try:
                    client.like(post.uri, post.cid)
                    print(f"❤️ いいね成功: @{post.author.handle} の投稿")
                    count += 1
                    time.sleep(3) # スパム防止
                except Exception:
                    continue
            
            if count > 0:
                print(f"✨ キーワード「{kw}」で {count}件にいいねしました。")
                
        except Exception as e:
            print(f"❌ 「{kw}」の検索・いいね中にエラーが発生: {e}")

def follow_active_users(client: Client):
    """キーワードで投稿しているアクティブなユーザーを検索してフォローする"""
    print(f"🔍 キーワードに関連するアクティブユーザーを探索・フォロー中... {KEYWORDS}")
    
    # 自分の情報を取得して、既にフォローしている人を確認
    try:
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

        total_follow_count = 0
        MAX_FOLLOW_PER_RUN = 10 # 1回の実行での最大フォロー数（安全のため）

        for kw in KEYWORDS:
            if total_follow_count >= MAX_FOLLOW_PER_RUN:
                break
                
            try:
                # キーワードで投稿を検索
                search_results = client.app.bsky.feed.search_posts(params={'q': kw, 'limit': 5})
                
                for post in search_results.posts:
                    author_did = post.author.did
                    author_handle = post.author.handle

                    if author_did != profile.did and author_did not in following_dids:
                        print(f"➕ 関連ユーザーをフォローします: @{author_handle}")
                        try:
                            client.follow(author_did)
                            following_dids.add(author_did) # 重複フォロー防止
                            total_follow_count += 1
                            time.sleep(5) # スパム防止のため長めに待機
                            
                            if total_follow_count >= MAX_FOLLOW_PER_RUN:
                                break
                        except Exception as e:
                            print(f"⚠️ フォロー失敗 (@{author_handle}): {e}")
                    
            except Exception as e:
                print(f"❌ 「{kw}」のユーザー探索中にエラーが発生: {e}")

        print(f"✅ 合計 {total_follow_count}人の新規ユーザーをフォローしました。")
    except Exception as e:
        import traceback
        print(f"❌ 関連ユーザーの探索・フォロー処理全体でエラーが発生しました: {e}")
        traceback.print_exc()

def main():
    if not BLUESKY_HANDLE or not BLUESKY_PASSWORD:
        print("❌ .envファイルが正しく設定されていません。")
        return

    client = Client()
    try:
        client.login(BLUESKY_HANDLE, BLUESKY_PASSWORD)
        print(f"✅ ログイン成功: @{BLUESKY_HANDLE}")
    except Exception as e:
        print(f"❌ ログインエラー: {e}")
        return

    # 1. 自動フォロバ
    follow_back(client)
    
    # 2. 自動キーワードいいね
    like_by_keywords(client)

    # 3. 関連ユーザーの自動フォロー（NEW!）
    follow_active_users(client)

    print("\n🎉 本日の積極的アクションが完了しました！")

if __name__ == "__main__":
    main()
