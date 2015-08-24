
from threading import Thread
from urllib import urlopen
from random import randint, choice
from time import sleep
from chat import Building
from webbrowser import open as browse


class TestClient(Thread):
    
    def __init__(self, index):
        self.index = str(index)
        Thread.__init__(self)
        
    def run(self):
        global errors
        try:
            urlopen("%s/body?user=testload-%s" % (
            choice(building.rooms).address_string, self.index)).read()
        except Exception, e:
            #print e
            errors += 1


errors = 0
building = Building("", 80)
for room in building.rooms:
    room.log = lambda message: None
building.start()


print "running"
for i in xrange(0, 1000):
    client = TestClient(i)
    client.start()


print "errors %s" % errors