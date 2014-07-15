# -*- coding: utf-8 -*-
from django.conf.urls import patterns, include, url
from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
admin.autodiscover()

urlpatterns = patterns('',
    # Examples:
    # url(r'^$', 'booksite.views.home', name='home'),
    # url(r'^blog/', include('blog.urls')),
    url(r'^$', 'booksite.book.views.home', name='home'),
    url(r'^book/(?P<book_id>\d+)/$', 'booksite.book.views.bookindex', name='bookindex'),
    url(r'^bookindex/(?P<book_id>\d+)/$', 'booksite.book.views.bookindexajax', name='bookindexajax'),
    url(r'^page/(?P<page_number>\d+)/$', 'booksite.book.views.bookpage', name='bookpage'),
    url(r'^admin/', include(admin.site.urls)),

)

if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)