from __future__ import absolute_import

from pylama.lint import Linter as BaseLinter

import pygql_checker
from pygql_checker import ImportOrderChecker


class Linter(ImportOrderChecker, BaseLinter):
    name = "pygql"
    version = pygql_checker.__version__

    def __init__(self):
        super(Linter, self).__init__(None, None)

    def allow(self, path):
        return path.endswith(".py")

    def error(self, node, code, message):
        lineno, col_offset = node.lineno, node.col_offset
        return {
            "lnum": lineno,
            "col": col_offset,
            "text": message,
            "type": code
        }

    def run(self, path, **meta):
        self.filename = path
        self.tree = None
        self.options = dict(
            {'schema': ''},
            **meta)

        for error in self.check_pygql():
            yield error
