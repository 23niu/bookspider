# -*- coding: utf-8 -*-
from __future__ import unicode_literals
import time
from django.shortcuts import render, get_object_or_404
from django.template.loader import render_to_string
from django.template import RequestContext
from django.views.generic import TemplateView
from django.http import Http404, HttpResponse
from django.core.paginator import Paginator
from django.views.decorators.cache import cache_page
from django.contrib.auth.decorators import login_required
from django.core.cache import cache

from booksite.ajax import ajax_success, ajax_error
from .models import Book, BookPage, BookRank
from .tasks import update_page, update_book_pic_page

home = TemplateView.as_view(template_name="book/index.html")


def home(request):
    C = {}
    books = Book.objects.all().order_by('book_number')
    if request.GET.get('s',''):
        books = books.filter(title__contains=request.GET['s'])
        C['search'] = True
    if request.GET.get('a',''):
        books = Book.objects.filter(author=request.GET['a'])
        C['author'] = request.GET['a']
        if not books:
            raise Http404
    p = Paginator(books, 30)
    try:
        page = p.page(int(request.GET.get('p', 1)))
    except:
        page = p.page(1)
    C['books'] = page.object_list
    C['pagination'] = page
    return render(request, 'book/index.html', C)

def mb_index(request):
    C = {}
    books = Book.objects.all().order_by('book_number')
    if request.GET.get('s',''):
        books = books.filter(title__contains=request.GET['s'])
        C['search'] = True
    if request.GET.get('a',''):
        books = Book.objects.filter(author=request.GET['a'])
        C['author'] = request.GET['a']
        if not books:
            raise Http404
    p = Paginator(books, 30)
    try:
        page = p.page(int(request.GET.get('p', 1)))
    except:
        page = p.page(1)
    C['books'] = page.object_list
    C['pagination'] = page
    return render(request, 'bookhtml5/base.html', C)

def category(request, category):
    CATEGORYS = {
        "a":"侦探推理",
        "b":"武侠修真",
        "c":"网游动漫",
        "d":"历史军事",
        "e":"都市言情",
        "f":"散文诗词",
        "g":"玄幻魔法",
        }
    if category not in CATEGORYS:
        raise Http404
    books = Book.objects.filter(category=CATEGORYS[category])
    C = {}
    p = Paginator(books, 30)
    try:
        page = p.page(int(request.GET.get('p', 1)))
    except:
        page = p.page(1)
    C['books'] = page.object_list
    C['pagination'] = page
    C['category'] = CATEGORYS[category]
    C['categorynav'] = "nav%s" % category
    return render(request, 'book/index.html', C)


def bookindex(request, book_id=0):
    if book_id == 0:
        raise Http404
    book = get_object_or_404(Book, pk=book_id)
    bookpages = BookPage.objects.filter(book_number=book.book_number).order_by('page_number')
    C = {}
    C['book'] = book
    C['bookpages'] = bookpages
    return render(request, 'book/bookindex.html', C)


def mb_bookindex(request, book_id=0):
    if book_id == 0:
        raise Http404
    book = get_object_or_404(Book, pk=book_id)
    bookpages = BookPage.objects.filter(book_number=book.book_number).order_by('page_number')
    C = {}
    C['book'] = book
    C['bookpages'] = bookpages
    return render(request, 'bookhtml5/bookindex.html', C)


@cache_page(60*60)
def bookindexajax(request, book_id=0):
    if book_id == 0:
        raise Http404
    book = get_object_or_404(Book, pk=book_id)
    bookpages = BookPage.objects.filter(book_number=book.book_number).order_by('page_number')
    C = {'bookpages': bookpages}
    data = render_to_string('book/bookindexajax.html', C)
    return HttpResponse(data)

def bookpage(request, page_number=0):
    if request.GET.get('invert',False):
        request.session['invert'] = not request.session.get('invert', False)
        return HttpResponse('')
    if page_number == 0:
        raise Http404
    bookpage = get_object_or_404(BookPage, page_number=page_number)
    book = get_object_or_404(Book, book_number=bookpage.book_number)
    # 注册用户的点击数据统计
    if request.user.is_authenticated():
        skey = 'time-book-%d'%book.pk
        now = int(time.time())
        timeold = request.session.setdefault(skey,now)
        if (now-timeold) > 21600:
            request.session[skey] = now
            book.get_bookrank().add_point()
        elif now == timeold:
            book.get_bookrank().add_point()
    C = {}
    C['book'] = book
    C['bookpage'] = bookpage
    C['invert'] = request.session.get('invert', False)
    return render(request, 'book/bookpage.html', C)


def mb_bookpage(request, page_number=0):
    if request.GET.get('invert',False):
        request.session['invert'] = not request.session.get('invert', False)
        return HttpResponse('')
    if page_number == 0:
        raise Http404
    bookpage = get_object_or_404(BookPage, page_number=page_number)
    book = get_object_or_404(Book, book_number=bookpage.book_number)
    # 注册用户的点击数据统计
    if request.user.is_authenticated():
        skey = 'time-book-%d'%book.pk
        now = int(time.time())
        timeold = request.session.setdefault(skey,now)
        if (now-timeold) > 21600:
            request.session[skey] = now
            book.get_bookrank().add_point()
        elif now == timeold:
            book.get_bookrank().add_point()
    C = {}
    C['book'] = book
    C['bookpage'] = bookpage
    C['invert'] = request.session.get('invert', False)
    return render(request, 'bookhtml5/bookpage.html', C)


def bookrank(request):
    C = {}
    model_fields_dict = dict(map(lambda x:(x.name,x), BookRank._meta._field_name_cache))
    model_fields_dict.pop('book')
    sort_key = request.GET.get("s", None)
    if model_fields_dict.has_key(sort_key):
        bookranks = BookRank.objects.all().order_by("-%s" % sort_key, "-all_point", "book__pk")
    else:
        bookranks = BookRank.objects.all().order_by("-all_point", "book__pk")
    p = Paginator(bookranks, 30)
    try:
        page = p.page(int(request.GET.get('p', 1)))
    except:
        page = p.page(1)
    C['bookranks'] = page.object_list
    C['pagination'] = page
    return render(request, 'book/bookrank.html', C)

def load_nall_page(request, page_id=0):
    bookpage = BookPage.objects.get(pk=page_id)
    book = Book.objects.get(book_number=bookpage.book_number)
    bookpages = []
    next_page_number = bookpage.next_number
    # 使用链式获取比排序后截取快
    for i in range(10):
        try:
            next_page = BookPage.objects.get(page_number=next_page_number)
        except:
            break
        else:
            bookpages.append(next_page)
            next_page_number = next_page.next_number

    data = render_to_string(
        'book/pagecontent.html',
        {
            'bookpages': bookpages,
            'book': book,
            'invert': request.session.get('invert', False),
        },
        context_instance=RequestContext(request)
    )
    return ajax_success(data)

@login_required
def page_fix_pic(request, page_id=0):
    if not request.user.is_superuser:
        raise Http404
    bookpage = get_object_or_404(BookPage, pk=page_id)
    title = bookpage.title
    book_title = bookpage.book.title
    update_page.delay(page_id, book_title, title)
    cache.set("pagetask-%s" % page_id, 'RUN', 600)
    return ajax_success()

@login_required
def page_task_check(request, page_id=0):
    if not request.user.is_superuser:
        raise Http404
    get_object_or_404(BookPage, pk=page_id)
    status = cache.get("pagetask-%s" % page_id)
    if status:
        return ajax_success(data={'status':status})
    else:
        return ajax_error('未知的任务')

@login_required
def book_fix_pic(request, book_id=0):
    if not request.user.is_superuser:
        raise Http404
    book = get_object_or_404(Book, pk=book_id)
    update_book_pic_page.delay(book.book_number, 200)
    return ajax_success()

