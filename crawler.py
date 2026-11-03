import requests
import json
import pandas as pd
import time
import random
import os

from bs4 import BeautifulSoup
from urllib.parse import urljoin


"""
CRAWLER using Web Scraping.
Main Source (TruyenQQ): https://truyenqqko.com/doc-truyen (HTML: view-source:https://truyenqqko.com/doc-truyen) ~ 18,700 rows.
Extra Source if you need (Nettruyen): https://hinettruyen.com/trang-chu/ (HTML: view-source:https://hinettruyen.com/trang-chu/) ~ 27,900 rows.
Request Time Modification: pages: time.sleep(0.5) - books: time.sleep(random.uniform(0.7, 1.3)).
Use break to stop the loop or continue to skip the current book when an error occurs.
"""


# =====================================================
# 1. FETCHER
# =====================================================

class Fetcher:

    def __init__(self):
        self.session = requests.Session()

        self.session.headers.update({
            "User-Agent": "Mozilla/5.0"
        })

    def fetch(self, url):
        response = self.session.get(
            url,
            timeout=15
        )

        response.raise_for_status()

        return response.text


# =====================================================
# 2. PARSER
# =====================================================

class TruyenParser:

    def parse_list_page(self, html):
        soup = BeautifulSoup(html, "html.parser")

        book_tags = soup.select("li:has(.book_avatar)")

        books = []

        for book_tag in book_tags:

            title_tag = book_tag.select_one(
                ".book_name h3 a"
            )

            cover_tag = book_tag.select_one(
                ".book_avatar img"
            )

            chapter_tag = book_tag.select_one(
                ".last_chapter a"
            )

            if not title_tag:
                continue

            book = {
                "title": title_tag.get_text(strip=True),
                "url": urljoin(
                    "https://truyenqqko.com",
                    title_tag.get("href", "")
                ),
                "cover_url": (
                    cover_tag.get("src")
                    if cover_tag else None
                ),
                "latest_chapter": (
                    chapter_tag.get_text(strip=True)
                    if chapter_tag else None
                )
            }

            books.append(book)

        return books

    def parse_detail_page(self, html):
        soup = BeautifulSoup(html, "html.parser")

        # Đọc JSON-LD
        json_ld = {}

        json_ld_tag = soup.find(
            "script",
            type="application/ld+json"
        )

        if json_ld_tag:
            try:
                json_ld = json.loads(
                    json_ld_tag.get_text()
                )
            except json.JSONDecodeError:
                pass

        # Lấy dữ liệu theo nhãn
        def get_info_value(label):

            for li in soup.select(".list-info li"):

                name_tag = li.select_one(".name")

                if (
                    name_tag
                    and label in name_tag.get_text(strip=True)
                ):

                    value_tag = li.select_one(
                        "p.col-xs-9"
                    )

                    if value_tag:
                        return value_tag.get_text(strip=True)

            return None

        # Tên truyện
        title_tag = soup.select_one(
            'h1[itemprop="name"]'
        )

        title = (
            title_tag.get_text(strip=True)
            if title_tag
            else json_ld.get("name")
        )

        # Genres
        genres = json_ld.get("genre", [])

        if isinstance(genres, str):
            genres = [genres]

        # Tác giả
        author_tag = soup.select_one(
            ".list-info li.author a.org"
        )

        author = (
            author_tag.get_text(strip=True)
            if author_tag
            else None
        )

        # Nhóm dịch
        team_tag = soup.select_one(
            ".list-info li.team a"
        )

        translation_team = (
            team_tag.get_text(strip=True)
            if team_tag
            else None
        )

        # Lượt thích
        likes_tag = soup.select_one(
            ".number-like"
        )

        likes = (
            likes_tag.get_text(strip=True)
            if likes_tag
            else None
        )

        return {
            "title": title,
            "genres": genres,
            "author": author,
            "created_date": get_info_value("Ngày tạo"),
            "translation_team": translation_team,
            "age_rating": get_info_value("Độ tuổi"),
            "likes": likes,
            "followers": get_info_value("Lượt theo dõi"),
            "views": get_info_value("Lượt xem")
        }


# =====================================================
# 3. STORAGE
# =====================================================

class Storage:

    def save_json(self, data, filepath):

        with open(
            filepath,
            "w",
            encoding="utf-8"
        ) as file:

            json.dump(
                data,
                file,
                ensure_ascii=False,
                indent=4
            )

        print(f"Đã lưu JSON: {filepath}")

    def save_csv(self, data, filepath):

        df = pd.DataFrame(data)

        if "genres" in df.columns:

            df["genres"] = df["genres"].apply(
                lambda x: ", ".join(x)
                if isinstance(x, list)
                else x
            )

        df.to_csv(
            filepath,
            index=False,
            encoding="utf-8-sig"
        )

        print(f"Đã lưu CSV: {filepath}")


# =====================================================
# 4. CHECKPOINT
# =====================================================

class Checkpoint:

    def __init__(self, filepath="checkpoint.json"):

        self.filepath = filepath

        self.data = {
            "processed_pages": [],
            "all_books": [],
            "completed_urls": [],
            "all_details": []
        }

        self.load()

    def load(self):

        if not os.path.exists(self.filepath):

            print("Chưa có checkpoint. Bắt đầu mới.")

            return

        try:

            with open(
                self.filepath,
                "r",
                encoding="utf-8"
            ) as file:

                self.data = json.load(file)

            print("\nĐã khôi phục checkpoint!")

            print(
                "Số trang đã xử lý:",
                len(self.data["processed_pages"])
            )

            print(
                "Số truyện đã thu thập:",
                len(self.data["completed_urls"])
            )

        except (json.JSONDecodeError, OSError, KeyError) as error:

            raise RuntimeError(
                f"Không thể đọc checkpoint: {error}"
            ) from error

    def save(self):

        temp_filepath = self.filepath + ".tmp"

        with open(
            temp_filepath,
            "w",
            encoding="utf-8"
        ) as file:

            json.dump(
                self.data,
                file,
                ensure_ascii=False,
                indent=4
            )

            file.flush()
            os.fsync(file.fileno())

        os.replace(
            temp_filepath,
            self.filepath
        )

    def add_page(self, page_number, books):

        existing_urls = {
            book["url"]
            for book in self.data["all_books"]
        }

        for book in books:

            if book["url"] not in existing_urls:

                self.data["all_books"].append(book)

                existing_urls.add(book["url"])

        self.data["processed_pages"].append(page_number)

        self.save()

    def add_detail(self, detail):

        url = detail["url"]

        if url not in self.data["completed_urls"]:

            self.data["all_details"].append(detail)

            self.data["completed_urls"].append(url)

            self.save()

    def is_page_completed(self, page_number):

        return page_number in self.data["processed_pages"]

    def is_url_completed(self, url):

        return url in self.data["completed_urls"]


# =====================================================
# 5. CRAWLER
# =====================================================

class TruyenCrawler:

    def __init__(self):

        self.fetcher = Fetcher()
        self.parser = TruyenParser()
        self.storage = Storage()
        self.checkpoint = Checkpoint()

        self.base_url = (
            "https://truyenqqko.com/truyen-moi-cap-nhat/trang-{}"
        )

    def crawl_page(self, page_number):

        url = self.base_url.format(page_number)

        print(
            f"\nĐang lấy trang danh sách {page_number}..."
        )

        html = self.fetcher.fetch(url)

        books = self.parser.parse_list_page(html)

        print(
            f"Tìm thấy {len(books)} truyện."
        )

        return books

    def crawl_detail(self, book):

        print(
            f"Đang lấy chi tiết: {book['title']}"
        )

        html = self.fetcher.fetch(book["url"])

        detail = self.parser.parse_detail_page(html)

        return {
            **book,
            **detail
        }

    def run(self, start_page=1, end_page=2):

        # =============================================
        # GIAI ĐOẠN 1: LẤY DANH SÁCH TRUYỆN
        # =============================================

        print("\n========== GIAI ĐOẠN 1 ==========")

        for page_number in range(
            start_page,
            end_page + 1
        ):

            if self.checkpoint.is_page_completed(page_number):

                print(
                    f"Bỏ qua trang {page_number}: đã hoàn thành."
                )

                continue

            try:

                books = self.crawl_page(page_number)

                self.checkpoint.add_page(
                    page_number,
                    books
                )

                time.sleep(0.5)

            except requests.RequestException as error:

                print(
                    f"Lỗi trang {page_number}: {error}"
                )

                break

        all_books = self.checkpoint.data["all_books"]

        print(
            "\nTổng số truyện tìm thấy:",
            len(all_books)
        )

        # =============================================
        # GIAI ĐOẠN 2: LẤY CHI TIẾT TRUYỆN
        # =============================================

        print("\n========== GIAI ĐOẠN 2 ==========")

        for index, book in enumerate(
            all_books,
            start=1
        ):

            url = book["url"]

            if self.checkpoint.is_url_completed(url):

                continue

            try:

                detail = self.crawl_detail(book)

                self.checkpoint.add_detail(detail)

                completed = len(
                    self.checkpoint.data["completed_urls"]
                )

                total = len(all_books)

                print(
                    f"Hoàn thành: {completed}/{total}"
                )

                time.sleep(random.uniform(0.7, 1.3))

            except requests.RequestException as error:

                print(
                    f"Lỗi khi lấy {book['title']}: {error}"
                )

                continue

        # =============================================
        # GIAI ĐOẠN 3: LƯU DỮ LIỆU
        # =============================================

        all_details = self.checkpoint.data["all_details"]

        if all_details:

            self.storage.save_json(
                all_details,
                "truyenqq_data.json"
            )

            self.storage.save_csv(
                all_details,
                "truyenqq_data.csv"
            )

        # =============================================
        # THỐNG KÊ
        # =============================================

        print("\n========== KẾT THÚC ==========")

        print(
            "Số trang đã xử lý:",
            len(self.checkpoint.data["processed_pages"])
        )

        print(
            "Tổng số truyện:",
            len(all_books)
        )

        print(
            "Số truyện đã hoàn thành:",
            len(all_details)
        )

        print(
            "Số truyện còn lại:",
            len(all_books) - len(all_details)
        )


# =====================================================
# 6. MAIN
# =====================================================

def main():

    crawler = TruyenCrawler()

    crawler.run(
        start_page=1,
        end_page=447
    )


if __name__ == "__main__":
    main()