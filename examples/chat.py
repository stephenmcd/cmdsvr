
import __init__
from time import sleep, strftime
from uuid import uuid4
from cmdsvr.packages.BeautifulSoup import BeautifulSoup
from cmdsvr import CommandServer, Command


rooms = ["Lobby", "Elevator", "Penthouse", "Pool", "Library", "Bar"]
entry_text = "enters"
exit_text = "leaves"
entry_id = str(uuid4())
exit_id = str(uuid4())
allowed = ["b", "i"]
actions = ["says"]
private = "whispers"


def strip_html(data, allowed=None):
    """strips html tags, keeping list of allowed"""

    if not allowed: allowed = []
    allowed = zip(["<%s" % t for t in allowed] + ["</%s>" % t
        for t in allowed], [str(uuid4()) for tag in allowed * 2])
    for tag, holder in allowed:
        data = data.replace(tag, holder)
    data = "".join(BeautifulSoup(data).findAll(text=True))
    for tag, holder in allowed:
        data = data.replace(holder, tag)
    return data

def user(command):
    """user command decorator"""

    def _user(self, request, **args):
        id = strip_html(args.get("user", ""))
        if not id:
            request.response.redirect("/")
            return
        if id not in self.users:
            # new user
            self.users[id] = {"name": strip_html(args["user"], allowed),
                "id": id, "session_id": request.session["id"], "messages":[]}
            self.add_message(entry_id, id)
        if self.users[id]["session_id"] != request.session["id"]:
            request.response.error("Name in use")
        else:
            args["user"] = self.users[id]
            command(self, request, **args)
    return _user


class Room(CommandServer):

    def __init__(self, host="", port="", name="Default", building=None):

        CommandServer.__init__(self, host, port)
        self.name = name
        self.port = port
        self.users = {}
        self._building = building

    def add_message(self, message, user_from, user_to="", action=""):
        """sends a new message to each applicable user"""

        if message:
            message = strip_html(message, allowed)
            if message == entry_id:
                message = " %s" % entry_text
            elif message == exit_id:
                message = " %s" % exit_text
            elif (action in actions + [private] and user_to in self.users):
                message = " <i>%s to %s</i>: %s" % (action, user_to, message)
            else:
                message = ": %s" % message
            message = "[%s] %s%s" % (strftime("%H:%M:%S"),
                self.users[user_from]["name"], message)
            for user in self.users.values():
                if action != private or user["id"] in (user_from, user_to):
                    user["messages"].append(message)
            if self._building:
                message = message.replace("]", "] [%s]" % self.name, 1)
            self.log(message)

    def log(self, message):
        """prints each room's messages"""

        print message

    @Command()
    def index(self, request):
        """display login page"""

        request.response.render("chat/login.html", room=self)

    @Command(user)
    def body(self, request, user=None):
        """streams response every second for <<x>> seconds"""

        request.response.write("\n" * 10000)
        connected = True
        while connected:
            if user["messages"]:
                connected = request.response.render("chat/message.html",
                    message=user["messages"].pop(0))
            else:
                connected = request.response.write("")
            sleep(.1)
        self.add_message(exit_id, user["id"])
        del self.users[user["id"]]

    @Command(user)
    def head(self, request, user=None, message="", to="", action=""):
        """renders the message entry page"""

        logout = self.address_string
        if self._building: logout = self._building.address_string
        self.add_message(message, user["id"], to, action)
        request.response.render("chat/head.html", user=user, to=to,
            action=action, actions=actions + [private],
            users=self.users.values(), logout=logout)

    @Command(user)
    def main(self, request, user=None):
        """renders the frameset page"""

        request.response.render("chat/room.html", user=user, room=self)


class Building(CommandServer):

    def __init__(self, host="", port=""):
        """create each room server"""

        self.rooms = [Room(port=8000 + i, name=name, building=self)
            for i, name in enumerate(rooms)]
        for room in self.rooms:
            room.session_timeout = 1
            room.start()
        CommandServer.__init__(self, host, port)

    @Command()
    def index(self, request):
        """display room lists"""

        request.response.render("chat/roomlist.html", rooms=self.rooms)


if __name__ == "__main__":
    import sys
    server = Building(*(sys.argv + [":80"])[1:][0].split(":"))
    server.start()