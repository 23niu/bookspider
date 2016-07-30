# -*- coding: utf-8 -*-
from __future__ import print_function
import re
import os
import site
import time
import difflib
import requests
import urlparse
import subprocess
from pyquery import PyQuery as PQ

from celery import shared_task
from django.core.cache import cache
from django.conf import settings

from booksite.book.models import BookPage, Book

# def update_book(book_number):
#     subprocess.Popen("/root/Envs/book/bin/scrapy \
#       parse http://www.86696.cc/book/%d.html \
#       --depth 4 --pipelines --noitems --nolinks -L ERROR" % book_number)


class RequestError(Exception):
    pass


def cmppmax(sa, sb):
    """获取字符串最大匹配长度,用来对比查找章节标题"""
    s = difflib.SequenceMatcher(None, sa, sb)
    max_len = 0
    for tag, i1, i2, j1, j2 in s.get_opcodes():
        if tag == 'equal':
            max_len = i2-i1 if i2-i1 > max_len else max_len
    return max_len


class KuaiYan(object):
    """快眼看书的章节提取"""
    def __init__(self, book_title):
        self.book_title = book_title
        self.headers = {
            'Accept': "text/html,application/xhtml+xml,\
                application/xml;q=0.9,image/webp,*/*;q=0.8",
            'User-Agent': "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_9_4)\
                AppleWebKit/537.36 (KHTML, like Gecko) Chrome/36.0.1985.125 Safari/537.36"
        }
        self._get_book_index()

    def _get_book_index(self):
        """从 '快眼看书' 获得指定书名的书籍目录."""
        data = {"searchkey": self.book_title.encode("gbk"), "searchtype": "articlename"}
        url = "http://www.yankuai.com/so/"
        search_book_req = requests.get(url, params=data, headers=self.headers)
        search_book_req.encoding = 'gbk'
        if not search_book_req.history:
            raise RequestError("Book not found! status_code: %s" % search_book_req.status_code)
        jq = PQ(search_book_req.text)
        book_index_url = jq(".btnlink")[0].attrib['href']
        book_index_req = requests.get(book_index_url, headers=self.headers)
        book_index_req.encoding = 'gbk'
        self.book_index_jq = PQ(book_index_req.text)("li>a")
        self.book_index_url = book_index_req.url

    def get_page_content(self, page_title):
        """获取章节内容"""
        match_a = None
        match_a_max_len = 0
        for i, elem in enumerate(self.book_index_jq):
            match_len = cmppmax(page_title, elem.text)
            if match_len > match_a_max_len:
                match_a_max_len = match_len
                match_a = elem
        page_url = urlparse.urljoin(self.book_index_url, match_a.attrib["href"])
        page_req = requests.get(page_url, headers=self.headers)
        page_req.encoding = 'gbk'
        jq = PQ(page_req.text)
        jq("#content>center").remove()
        content = jq("#content").text().replace(" ", "\n")
        rp = re.compile(ur".*(\(手打中文.*\)).*")
        for i in rp.findall(content):
            content = content.replace(i, '')
        return "%s\n\n%s" % (match_a.text, content)


@shared_task
def update_page(page_id, book_title, page_title):
    """更新指定章节的内容"""
    spider = KuaiYan(book_title)
    content = spider.get_page_content(page_title)
    page = BookPage.objects.get(pk=page_id)
    page.content = content
    page.save()
    cache.set("pagetask-%s" % page_id, 'DONE', 600)
    return content


@shared_task
def update_book_pic_page(book_number, page_min_length):
    """更新指定书籍的图片章节,按照page_min_length判断章节长度,小于此长度则更新."""
    book = Book.objects.get(book_number=book_number)
    spider = KuaiYan(book.title)
    pages = BookPage.objects.filter(book_number=book_number)
    for page in pages:
        if len(page.content) < page_min_length:
            content = spider.get_page_content(page.title)
            page.content = content
            page.save()
    return list(pages.values_list("pk", flat=True))


@shared_task
def get_new_book_with_book_name(book_name):
    """根据书名获取新书内容"""
    # Base env
    scrapy_project_path = getattr(settings, 'SCRAPY_PROJECT', None)
    if scrapy_project_path is None:
        raise UserWarning("SCRAPY_PROJECT not configured!")
    if not os.path.exists(os.path.join(scrapy_project_path, 'scrapy.cfg')):
        raise UserWarning("SCRAPY_PROJECT not exists!")
    # GET book_url from 86696, if has many book then raise error.
    params = {"searchkey": book_name.encode("GBK"),
            "searchtype": "articlename"}
    res = requests.get("http://www.86696.cc/modules/article/search.php", params=params, allow_redirects=False)
    if res.status_code != 302:
        raise UserWarning("Search result is not one book! %s" % book_name)
    book_url = res.headers['location']

    # Start scrapy
    scrapy_bin = os.path.join(site.PREFIXES[0], "bin/scrapy")
    spider = subprocess.Popen([
        scrapy_bin,
        'crawl',
        '-L',
        'ERROR',
        'douluo',
        '-a',
        'starturl=%s' % book_url
    ], cwd=scrapy_project_path)
    start_time = time.time()
    while spider.returncode == None:
        time.sleep(1)
        if time.time() - start_time > 200.00:
            print("\nTimeout!")
            spider.kill()
            print("Killed!")
            break
