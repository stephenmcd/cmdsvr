
from cmdsvr import CommandServer, Command
from time import sleep


class TestServer(CommandServer):
    
    @Command()
    def echo(self, request, text=""):
        """prints out text <<x>>"""
        request.response.write(text)
    
    @Command()
    def sleep(self, request, seconds):
        """go to sleep for <<x>> second"""
        try:
            seconds = int(seconds)
        except:
            seconds = 0
        request.response.write("Sleeping for %s seconds" % seconds)
        sleep(seconds)
        request.response.write("<br>Awake!")
    
    @Command()
    def stream(self, request, seconds=0):
        """streams response every second for <<x>> seconds"""
        try:
            seconds = int(seconds)
        except:
            seconds = 0
        request.response.write("Streaming for: %s seconds<br>%s" % 
            (seconds, " \n" * 100))
        while seconds:
            seconds -= 1
            if not request.response.write("Seconds left: %s<br>" % seconds):
                break
            sleep(1.)
        else:
            request.response.write("Done!")
        
    @Command()
    def headers(self, request):
        """print out http headers"""
        request.response.write("<br>".join(["%s: %s" % 
            (k, v) for k, v in request.headers.items()]))
    
    @Command()
    def quit(self, request, password):
        """shutdown the server"""
        if password == "devo123":
            request.response.write("Quitting!")
            super(TestServer, self).quit()
        else:
            request.response.write("Invalid password: %s" % password)
    
    @Command()
    def address(self, request):
        """display client address"""
        request.response.write(request.address_string())
        
    @Command()
    def redirect(self, request, url):
        """redirect to url"""
        request.response.redirect(url)
        
    @Command()
    def session(self, request):
        """lists session variable"""
        request.response.write("<br>".join(["%s: %s" % 
            (k, v) for k, v in request.session.items()]))
