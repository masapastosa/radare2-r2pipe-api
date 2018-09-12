from __future__ import print_function
import sys

from .base import R2Base, Result, ResultArray
from .debugger import Debugger
from .config import Config
from .file import File
from .print import Print
from .write import Write
from .flags import Flags
from .esil import Esil

try:
    import r2pipe
except ImportError:
    print("r2pipe not found")
    print("You can install it with pip: pip install r2pipe")
    raise ImportError("r2pipe not found")

PYTHON_VERSION = sys.version_info[0]


class Function(R2Base):

    def __init__(self, r2, addr):
        super(Function, self).__init__(r2)

        self.offset = addr

    def analyze(self):
        self._exec("af %s" % self.offset)

    def info(self):
        # XXX: Is this [0] always correct?
        res = self._exec("afij @ %s" % self.offset, json=True)[0]
        return Result(res)

    def rename(self, name):
        self._exec("afn %s %s" % (name, self.offset))

    @property
    def name(self):
        return self.info().name

    @name.setter
    def name(self, value):
        self.rename(value)


class R2Api(R2Base):

    def __init__(self, filename=None, r2=None):
        if filename is not None:
            r2 = r2pipe.open(filename)
        super(R2Api, self).__init__(r2)

        self.debugger = Debugger(r2)

        # Using 'print' in python2 raises a syntax error if print function
        # is not imported, _print can be used as an alternative.
        if PYTHON_VERSION == 2:
            self._print = Print(r2)
        self.print = Print(r2)

        self.write = Write(r2)
        self.config = Config(r2)
        self.flags = Flags(r2)
        self.esil = Esil(r2)

        self.info = lambda: Result(self._exec("ij", json=True))
        self.searchIn = lambda x: self._exec("e search.in=%s" % (x))
        self.analyzeAll = lambda: self._exec("aaa")
        self.analyzeCalls = lambda: self._exec("aac")
        self.basicBlocks = lambda: ResultArray(self._exec("afbj", json=True))
        self.xrefsAt = lambda: ResultArray(
            self._exec("axtj %s" % self._tmp_off, json=True)
        )
        self.refsTo = lambda: ResultArray(self._exec("axfj", json=True))
        self.opInfo = lambda: ResultArray(
            self._exec("aoj %s" % self._tmp_off, json=True)
        )[
            0
        ]
        self.seek = lambda x: self._exec("s %s" % (x))

    def __enter__(self):
        return self

    def __exit__(self, e_type, e_val, tb):
        self.quit()

    def open(self, filename, at="", perms=""):
        # See o?
        self._exec("o %s %s %s" % (filename, at, perms))

    @property
    def files(self):
        files = self._exec("oj", json=True)
        return [File(self.r2, f["fd"]) for f in files]

    def functionAt(self, at):
        res = self._exec("afo %s" % at)
        if res == "":
            return None
        return int(res, 16)

    def currentFunction(self):
        at = "$$"
        if self._tmp_off != "":
            at = self._tmp_off.split()[1]
        self._tmp_off = ""
        return self.functionAt(at)

    def functions(self):
        res = self._exec("aflj", json=True)
        return [Function(self.r2, f["offset"]) for f in res] if res else []

    def analyzeFunction(self):
        res = self._exec("af %s|" % (self._tmp_off))
        self._tmp_off = ""
        return res

    def disasmFunction(self):
        res = self._exec("pdr %s|" % (self._tmp_off))
        self._tmp_off = ""
        return res

    def functionByName(self, name):
        # Use list for python3 compatibility
        return list(filter(lambda x: x.name == name, self.functions()))

    def read(self, len):
        res = self._exec("p8 %s%s|" % (len, self._tmp_off))
        self._tmp_off = ""
        if PYTHON_VERSION == 3:
            return bytes.fromhex(res)
        else:
            return res.decode("hex")

    def __getitem__(self, k):
        if type(k) == slice:
            _from = k.start
            if type(k.start) == str:
                _from = self.sym_to_addr(k.start)

            _to = k.stop
            if type(k.stop) == str:
                _to = self.sym_to_addr(k.stop)

            read_len = _to - _from
            at_addr = _from
        else:
            read_len = 1
            at_addr = k
        return self.print.at(at_addr).bytes(read_len)

    def __setitem__(self, k, v):
        return self.write.at(k).bytes(v)

    def quit(self):
        self.r2.quit()
        self.r2 = None
