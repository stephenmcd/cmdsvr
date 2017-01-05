
from __future__ import with_statement
from BaseHTTPServer import HTTPServer, BaseHTTPRequestHandler
from SocketServer import ThreadingMixIn
from socket import error as sockerr
from threading import Thread, RLock
from urlparse import urlparse, urlunparse
from cgi import parse_qs
from inspect import getargspec, getmro, getsourcefile
from traceback import format_exc
from os.path import exists, dirname, sep, basename, join as pathjoin
from Cookie import SimpleCookie
from time import time
from uuid import uuid4
from UserDict import UserDict

from packages.Cheetah.Template import Template
from packages.pygments import highlight, lexers, formatters, filters


__version__ = "0.1"


class Command(object):
    """decorator for commands"""

    def __init__(self, *decorators):
        """store decorators"""

        self._decorators = decorators

    def __call__(self, *args, **kwargs):
        """bind command on first call and call command on subsequent calls"""

        if not hasattr(self, "_command"):
            self._command = args[0]
            self.module = self._command.__module__
            self.name = self._command.__name__
            self.doc = self._command.__doc__.replace("<<", "<code>").replace(
                ">>", "</code>") if self._command.__doc__ else "Undocumented"
            spec = getargspec(self._command)
            self.args = spec[0][2:]
            self.keywords = spec[-1] is not None
            self.sig = "%s%s%s" % (self.name, "?" if self.args else "",
                "&".join(["%s=%s" % (arg, arg) for arg in self.args]))
            for decorator in self._decorators:
                self._command = decorator(self._command)
            return self
        else:
            return self._command(*args, **kwargs)


class CommandResponse(object):
    """provides context for output to a request"""

    def __init__(self, request):
        """retrieves session id from cookie and push it back into the
        cookie after recreating it if session has expired"""

        self._request = request
        cookie = SimpleCookie(request.headers.get("cookie", ""))
        name = request.server.version_name
        if name in cookie: request.id = cookie[name].value
        cookie[name] = request.session["id"]
        cookie[name]["expires"] = 30 * 24 * 60 * 60 # 30 days
        request.id = cookie[name].value
        self._headers = {"Content-Type": "text/html",
            "Set-Cookie": cookie.output(header="")}

    def write(self, data, status=200):
        """write output to the response"""

        request = self._request
        request.session["last"] = time()
        try:
            if hasattr(self, "_headers"):
                request.send_response(status)
                for header in self._headers.items():
                    request.send_header(*header)
                request.end_headers()
                del self._headers
            request.wfile.write("\n%s" % data)
            return True
        except sockerr:
            return False
        except Exception, e:
            raise e

    def render(self, template, **data):
        """respond with template filled with data"""

        status = data.pop("status", 200)
        return self.write(Template(searchList=data,
            file=pathjoin(self._request.server.template_dir, template),
            compilerSettings={"useAutocalling": False}), status=status)

    def redirect(self, url):
        """send new location header to redirect to"""

        request = self._request
        url = list(urlparse(url))
        if not url[0]:
            url[0] = "http"
        if not url[1]:
            url[1] = request.server.address_string.split("://", 1)[1]
        request.send_response(302)
        request.send_header("Location", urlunparse(url))
        request.end_headers()

    def error(self, msg, status=500):
        """render the error template"""

        self.render("error.html", title="%s Error" % status,
            error=msg, status=status)


class CommandRequest(BaseHTTPRequestHandler):
    """request handler"""

    def do_GET(self):
        """map requested url to command and arguments"""

        # create response and parse url
        self.id = None
        self.response = CommandResponse(self)
        url = urlparse(self.path)
        qs = dict([(k, v[0]) for k, v in parse_qs(url.query).items()])
        command = url.path[1:]
        if not command: command = "index"
        commands = self.server._commands

        if command in commands:
            # run command
            command = commands[command]
            args = dict([(k, v) for k, v in qs.items() if k in command.args])
            try:
                command(self.server, self, **args)
            except Exception, e:
                self.response.error(format_exc().replace(dirname(__file__) +
                    sep, ""))
        elif exists(pathjoin(self.server.template_dir, "%s.html" % command)):
            # static file
            self.response.render("%s.html" % command)
        else:
            # invalid url
            self.response.error("Requested resource doesn't exist", status=404)

    @property
    def session(self):
        return self.server._sessions[self.id]

    def version_string(self):
        return "%s/%s" % (self.server.version_name, __version__)

    def log_message(self, *args):
        """pass logging to the server"""

        self.server.log_message(*args)


class SessionManager(UserDict):

    def __init__(self, server):
        """create lock"""

        self._lock = RLock()
        self._server = server
        UserDict.__init__(self)

    def __getitem__(self, id):
        """create a new session if id doesn't exist"""

        with self._lock:
            if id not in self.data:
                id = str(uuid4())
                self.data[id] = {"id": id}
                self._server.session_start(self.data[id])
            self.data[id]["last"] = time()
            return self.data[id]

    def expire(self, timeout, callback):
        """remove session older than timeout and pass them to the callback"""

        with self._lock:
            expired = [session for session in self.data.values()
                if session["last"] < time() - (timeout * 60.)]
            self.data = dict([(id, session) for id, session
                in self.data.iteritems() if session not in expired])
            map(callback, expired)


class CommandServer(ThreadingMixIn, HTTPServer, Thread):
    """http server with hook for shutting down"""

    def __init__(self, host="", port="80"):
        """bind commands"""

        HTTPServer.__init__(self, (host, int(port)), CommandRequest)
        Thread.__init__(self)

        self.version_name = self.__class__.__name__
        self.session_timeout = 20
        self.template_dir = pathjoin(dirname(__file__), "templates")
        self._running = True
        self._sessions = SessionManager(self)
        self._commands = dict([item for item in [(name, eval("self.%s" % name))
            for name in dir(self)] if hasattr(item[1], "_command")])

    def run(self):
        """start serving and run until quit is called"""

        self.address_string = "http://%s:%s" % (self.server_name,
            self.server_port)
        while self._running:
            self._sessions.expire(self.session_timeout, self.session_end)
            self.handle_request()

    def quit(self):
        """quit serving"""

        self._running = False

    def log_message(self, *args):
        """request logging - override"""
        pass

    def session_start(self, session):
        """session starting - override"""
        pass

    def session_end(self, session):
        """session ending - override"""
        pass

    @Command()
    def index(self, request, command=""):
        """display list of commands and docs
        with links to test forms for commands"""

        command = self._commands.get(command, None)
        if command:
            request.response.render("command.html", command=command)
        else:
            request.response.render("commands.html",
                commands=self._commands.values())

    @Command()
    def source(self, request):
        """display source code for server and sub classes"""

        source = []
        header = ("\n#" + (" " * 7) + "%s\n").join(["#" * 80] * 2)
        for cls in getmro(self.__class__):
            f = open(getsourcefile(cls), "r")
            source.extend([f.read(), header % basename(f.name).upper()])
            f.close()
            if cls == CommandServer: break
        source.reverse()
        lexer = lexers.get_lexer_by_name("python")
        lexer.add_filter(filters.VisibleWhitespaceFilter(tabs=" ", tabsize=4))
        request.response.write(highlight("\n\n".join(source), lexer,
            formatters.HtmlFormatter(linenos="inline", full=True)))


if __name__ == "__main__":
    import sys
    from examples.testserver import TestServer
    server = TestServer(*(sys.argv + [""])[1:][0].split(":"))
    server.start()
