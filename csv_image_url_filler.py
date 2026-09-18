"""
posts.csv の各行を走査し、本文に特定URLパターン（アフィリエイトリンク等）が
含まれる投稿に、画像URL列（image_url）を自動で補完するユーティリティ。

用途例: アフィリエイトASPのリンクを含む投稿だけに、共通のプレースホルダー
画像（またはASP指定のバナー画像URL）を付与したい場合に使用する。
"""
import csv
import os

CSV_PATH = os.path.join(os.path.dirname(__file__), "posts.csv")

# 本文にこの文字列を含む投稿にだけ image_url を設定する
TARGET_URL_PATTERN = "moshimo.com"
DUMMY_IMAGE_URL = "https://placehold.co/600x400/png?text=Affiliate+Image"


def main():
    posts = []
    with open(CSV_PATH, "r", encoding="utf-8-sig", newline="") as f:
        reader = csv.reader(f)
        header = next(reader)
        for row in reader:
            posts.append(row)

    if "image_url" not in header:
        header.append("image_url")
    image_url_idx = header.index("image_url")

    for row in posts:
        while len(row) < len(header):
            row.append("")
        if TARGET_URL_PATTERN in row[1]:
            row[image_url_idx] = DUMMY_IMAGE_URL

    with open(CSV_PATH, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(header)
        writer.writerows(posts)

    print("posts.csv modified successfully.")


if __name__ == "__main__":
    main()
