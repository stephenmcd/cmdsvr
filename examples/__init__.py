
# relative import hack
from sys import path
from os.path import dirname, abspath, join as pathjoin
path.append(abspath(pathjoin(dirname(__file__), "..", "..")))
