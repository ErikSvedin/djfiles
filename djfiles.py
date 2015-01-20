from __future__ import unicode_literals

import mimetypes
import os
import stat
import posixpath

from django.http import (Http404, HttpResponseRedirect, HttpResponseNotModified, FileResponse)
from django.utils.http import http_date
from django.utils.six.moves.urllib.parse import unquote
from django.utils.translation import ugettext as _


def serve(request, path, document_root=None, show_indexes=False):
    path = posixpath.normpath(unquote(path))
    path = path.lstrip('/')
    newpath = ''
    for part in path.split('/'):
        if not part:
            # Strip empty path components.
            continue
        drive, part = os.path.splitdrive(part)
        head, part = os.path.split(part)
        if part in (os.curdir, os.pardir):
            # Strip '.' and '..' in path.
            continue
        newpath = os.path.join(newpath, part).replace('\\', '/')
    if newpath and path != newpath:
        return HttpResponseRedirect(newpath)
    fullpath = os.path.join(document_root, newpath)
    if os.path.isdir(fullpath):
        raise Http404(_('Directory indexes are not allowed here.'))
    if not os.path.exists(fullpath):
        raise Http404(_('"%(path)s" does not exist') % {'path': fullpath})
    statobj = os.stat(fullpath)
    last_modified = http_date(statobj.st_mtime)
    if request.META.get('HTTP_IF_MODIFIED_SINCE') == last_modified:
        return HttpResponseNotModified()
    content_type, encoding = mimetypes.guess_type(fullpath)
    content_type = content_type or 'application/octet-stream'
    response = FileResponse(open(fullpath, 'rb'), content_type=content_type)
    response['Last-Modified'] = last_modified
    if stat.S_ISREG(statobj.st_mode):
        response['Content-Length'] = statobj.st_size
    if encoding:
        response['Content-Encoding'] = encoding
    return response


def ranges(request, path, document_root):
    path = posixpath.normpath(unquote(path))
    path = path.lstrip('/')
    newpath = ''
    for part in path.split('/'):
        if not part:
            # Strip empty path components.
            continue
        drive, part = os.path.splitdrive(part)
        head, part = os.path.split(part)
        if part in (os.curdir, os.pardir):
            # Strip '.' and '..' in path.
            continue
        newpath = os.path.join(newpath, part).replace('\\', '/')
    if newpath and path != newpath:
        return HttpResponseRedirect(newpath)
    fullpath = os.path.join(document_root, newpath)
    if os.path.isdir(fullpath):
        raise Http404(_('Directory indexes are not allowed here.'))
    if not os.path.exists(fullpath):
        raise Http404(_('"%(path)s" does not exist') % {'path': fullpath})
    statobj = os.stat(fullpath)
    last_modified = http_date(statobj.st_mtime)
    if request.META.get('HTTP_IF_MODIFIED_SINCE') == last_modified:
        return HttpResponseNotModified()
    content_type, encoding = mimetypes.guess_type(fullpath)
    content_type = content_type or 'application/octet-stream'
    f = open(fullpath, 'rb')
    start = 0
    end = statobj.st_size - 1
    http_range = request.META.get('HTTP_RANGE')
    if http_range and http_range.startswith('bytes=') and http_range.count('-') == 1:
        start, end = http_range[len('bytes='):].split('-')
        start, end = int(start or 0), int(end or statobj.st_size - 1)
        assert 0 <= start < statobj.st_size, start
        assert 0 <= end < statobj.st_size, end
        f.seek(start)
        old_read = f.read
        f.read = lambda n: old_read(min(n, end + 1 - f.tell()))
    else:
        http_range = None
    response = FileResponse(f, content_type=content_type, status=206 if http_range else 200)
    response['Last-Modified'] = last_modified
    if stat.S_ISREG(statobj.st_mode):
        response['Content-Length'] = end + 1 - start
        if http_range:
            response['Content-Range'] = 'bytes %d-%d/%d' % (start, end, statobj.st_size)
    if encoding:
        response['Content-Encoding'] = encoding
    return response


class Serve(object):

    def get(self, urlpath, *args, **kwargs):
        return self.find_and_serve(urlpath)

    def find_and_serve(self, urlpath):
        filepath = self.find(urlpath)
        return self.conditional_serve(filepath)

    def find(self, urlpath):
        fullpath = os.path.join(self.document_root, urlpath)
        if not os.path.exists(fullpath):
            raise Http404(_('"%(path)s" does not exist') % {'path': fullpath})
        return fullpath
    
    def conditional_serve(self, filepath):
        statobj = os.stat(filepath)
        last_modified = http_date(statobj.st_mtime)
        if self.request.META.get('HTTP_IF_MODIFIED_SINCE') == last_modified:
            return HttpResponseNotModified()
        response = self.serve(filepath)
        response['Last-Modified'] = last_modified
        return response

    def serve(self, filepath):
        return FileResponse(open(filepath, 'rb'))
