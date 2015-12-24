#!/usr/bin/env python3
# -*- coding:utf-8; mode:python3; indent-tabs-mode:nil; tab-width:4; -*-

""" Filter for PostiATS messages. """

import collections
import os.path
import sys

LINE_WIDTH = 78
SIMPLIFY = True
LOC_WITH_COLUMN = True
REL_PATH = True

# PostiATS Messages
# ============================================================================

# Type
# ----------------------------------------------------------------------------
Message = collections.namedtuple(
    "Message",
    ["path", "line", "col", "level", "text"])

# Constants
# ----------------------------------------------------------------------------
# Sample of message with location:
#     UTF_8.dats: 5235(line=167, offs=53) -- 5237(line=167, offs=55): \
#     error(3): static arity mismatch: more arguments are expected.

END_OF_PATH = ": "
LINE_TAG = "(line="
OFFS_TAG = ", offs="
END_OF_BEGIN = ") -- "
END_OF_END = "): "
END_OF_MSG_LEVEL = ": "

# Given these tags, the above sample would be split like this:
#
#  * "UTF_8.dats"   Path
#  * ": "           END_OF_PATH
#  * "5235"         Begin bytes
#  * "(line="       LINE_TAG
#  * "167"          Begin line
#  * ", offs="      OFFS_TAG
#  * "53"           Begin offset (column)
#  * ") -- "        END_OF_START
#  * "5237"         End bytes
#  * "(line="       LINE_TAG
#  * "167"          End line
#  * ", offs="      OFFS_TAG
#  * "55"           End offset (column)
#  * "): "          END_OF_END
#  * error(3)       Message level
#  * ": "           END_OF_MSG_LEVEL
#  * "static arity mismatch: more arguments are expected."  Message
#
# Tested and applied in this order (there are duplicates):
#
#  * END_OF_PATH
#  * LINE_TAG
#  * OFFS_TAG
#  * END_OF_START
#  * LINE_TAG
#  * OFFS_TAG
#  * END_OF_END
#  * END_OF_MSG_LEVEL


# Helper
# ----------------------------------------------------------------------------

def find_tag(line, tag, start):
    """ Tuple `(start, end)` of `tag` in `line` starting at `start`.

    If `tag` is not found, `(-1, end)` is returned.

    """
    i = line.find(tag, start)
    j = i + len(tag)
    result = (i, j)
    return result


# Methods
# ----------------------------------------------------------------------------

def is_message_with_location(line):
    """ True is line is a message with location. """
    j = 0

    def test_tag(tag):
        """ Update (i,j) if i is not -1. """
        nonlocal j
        (i, j) = find_tag(line, tag, j)
        result = i != -1
        return result

    result = (
        test_tag(END_OF_PATH)
        and test_tag(LINE_TAG)
        and test_tag(OFFS_TAG)
        and test_tag(END_OF_BEGIN)
        and test_tag(LINE_TAG)
        and test_tag(OFFS_TAG)
        and test_tag(END_OF_END)
        and test_tag(END_OF_MSG_LEVEL)
    )

    return result


def message_level_number(message_level):
    """ Level number from message level tag. """
    result = 0
    if message_level == "error(parsing)":
        result = 1
    if message_level == "error(2)":
        result = 2
    if message_level == "error(mac)":
        result = 2
    if message_level == "error(3)":
        result = 3
    return result


def parse_message_with_location(line):
    """ Parse `line` as a `Message`. """
    i = 0
    j = 0
    k = 0

    (j, k) = find_tag(line, END_OF_PATH, k)
    path = line[i:j]
    i = k

    (j, k) = find_tag(line, LINE_TAG, k)
    # start_bytes = line[i:j]
    i = k

    (j, k) = find_tag(line, OFFS_TAG, k)
    start_line = line[i:j]
    i = k

    (j, k) = find_tag(line, END_OF_BEGIN, k)
    start_offs = line[i:j]
    i = k

    (j, k) = find_tag(line, LINE_TAG, k)
    # end_bytes = line[i:j]
    i = k

    (j, k) = find_tag(line, OFFS_TAG, k)
    # end_line = line[i:j]
    i = k

    (j, k) = find_tag(line, END_OF_END, k)
    # end_offs = line[i:j]
    i = k

    (j, k) = find_tag(line, END_OF_MSG_LEVEL, k)
    message_level = line[i:j]
    i = k

    level = message_level_number(message_level)

    text = line[i:]

    if REL_PATH:
        path = os.path.relpath(path)

    result = Message(
        path=path,
        line=int(start_line),
        col=int(start_offs),
        level=level,
        text=text)

    return result


# Iterated String
# ============================================================================

class String(object):
    """ String iterator. """

    def __init__(self, string):
        """ Assign content to `string` and initializes index and stack. """
        self.string = string
        self.index = 0
        self.indexes = []
        self.len = len(string)

    def has_item(self):
        """ True if `item` is valid. """
        result = self.index < self.len
        return result

    def item(self):
        """ Character at index. """
        if not self.has_item():
            raise IndexError
        result = self.string[self.index]
        return result

    def has_ahead(self):
        """ True if `ahead` won't be `None`. """
        result = (self.index + 1) < self.len
        return result

    def ahead(self):
        """ Character next to actual `item` (may be `None`). """
        if not self.has_ahead():
            result = None
        else:
            result = self.string[self.index + 1]
        return result

    def consume(self):
        """ Consume current `item`: move index forward. """
        if not self.has_item():
            raise IndexError
        self.index += 1

    def push(self):
        """ Push current index on stack. """
        self.indexes.append(self.index)

    def unpush(self):
        """ Pop from stack not touching index. """
        if len(self.indexes) == 0:
            raise IndexError
        self.indexes.pop()

    def pop(self):
        """ Pop current index from stack. """
        if len(self.indexes) == 0:
            raise IndexError
        self.index = self.indexes.pop()

    def test_and_consume(self, string):
        """ True if `string` at index and skip, else False. """
        result = False
        i = self.index
        j = i + len(string)
        if self.string[i:j] == string:
            self.index = j
            result = True
        return result


# Parsing PostiATS's funny expressions
# ============================================================================

# Type
# ----------------------------------------------------------------------------
Node = collections.namedtuple("Node", ["token", "kind", "nodes", "end"])

# Constants
# ----------------------------------------------------------------------------
KIND_D2S2C3 = 1
KIND_NAME = 2
KIND_NAME_ID = 3
KIND_NUMERIC = 4
KIND_SYMBOL = 5

FOLLOWED_BY_SEMI_COLON = 1
FOLLOWED_BY_COMMA = 2
FOLLOWED_BY_ARROW = 3
FOLLOWED_BY_END = 4


# Methods
# ----------------------------------------------------------------------------

# ### S2/C3 Name Token

def parse_d2s2c3_name(string):
    """ An S2Xxxx or a C3Xxxx or None. """
    result = None
    prefix = None
    if string.test_and_consume("D2"):
        prefix = "D2"
    elif string.test_and_consume("S2"):
        prefix = "S2"
    elif string.test_and_consume("C3"):
        prefix = "C3"
    if prefix is not None:
        if string.has_item() and string.item().isalpha():
            result = prefix + string.item()
            string.consume()
            while string.has_item() and string.item().isalpha():
                result += string.item()
                string.consume()
    return result


# ### Numeric Token

def parse_numeric(string):
    """ A numeric or None. """
    result = None
    string.push()
    if string.has_item():
        sign = +1
        if string.item() == "-":
            sign = -1
            string.consume()
        if string.has_item() and string.item().isnumeric():
            result = string.item()
            string.consume()
            while string.has_item() and string.item().isnumeric():
                result += string.item()
                string.consume()
            if sign == -1:
                result = "-" + result
    if result is None:
        string.pop()
    else:
        string.unpush()
    return result


# ### Name Token

def is_name_head_char(char):
    """ Alpha or _. """
    result = char.isalpha() or char == "_"
    return result


def is_name_tail_char(char):
    """ Alnum or _ or '. """
    result = char.isalnum() or char == "_" or char == "'"
    return result


def parse_name(string):
    """ A name or None. """
    result = None
    if string.has_item() and is_name_head_char(string.item()):
        result = string.item()
        string.consume()
        while string.has_item() and is_name_tail_char(string.item()):
            result += string.item()
            string.consume()
    return result


# ### Name$ID Token

def parse_name_id(string):
    """ A name$id or None. """
    result = None
    string.push()
    name_part = parse_name(string)
    if name_part is not None:
        if string.test_and_consume("$"):
            id_part = parse_numeric(string)
            if id_part is not None:
                result = name_part + "$" + id_part
    if result is not None:
        string.unpush()
    else:
        string.pop()
    return result


# ### Symbol Token

def is_symbol_char(char):
    """ True if `char` is a symbol. """
    result = char in "[]<>.-+/%=~*&|"
    return result


def parse_symbol(string):
    """ A symbole or None. """
    result = None
    if string.has_item() and is_symbol_char(string.item()):
        result = string.item()
        string.consume()
        while string.has_item() and is_symbol_char(string.item()):
            result += string.item()
            string.consume()
    return result


# ### Token

def parse_token(string):
    """ `(token, kind)` or None. """

    def try_token(method, kind):
        """ (token, kind) or None. """
        result = None
        token = method(string)
        if token is not None:
            result = (token, kind)
        return result

    result = (
        try_token(parse_d2s2c3_name, KIND_D2S2C3)
        or try_token(parse_name_id, KIND_NAME_ID)
        or try_token(parse_name, KIND_NAME)
        or try_token(parse_numeric, KIND_NUMERIC)
        or try_token(parse_symbol, KIND_SYMBOL)
    )

    return result


# ### Node

def get_end_kind(string):
    """ End kind. """
    result = None
    if string.test_and_consume("; "):
        result = FOLLOWED_BY_SEMI_COLON
    elif string.test_and_consume(", "):
        result = FOLLOWED_BY_COMMA
    elif string.test_and_consume("->"):
        result = FOLLOWED_BY_ARROW
    else:
        result = FOLLOWED_BY_END
    return result


def parse_node(string):
    """ A Node or None. """
    result = None
    token = None
    kind = False
    nodes = None
    end = None
    token_kind = parse_token(string)
    if token_kind is not None:
        (token, kind) = token_kind
        if string.test_and_consume("("):
            nodes = parse_nodes(string)
            if nodes is not None and string.test_and_consume(")"):
                end = get_end_kind(string)
        else:
            end = get_end_kind(string)
    if end is not None:
        result = Node(
            token=token,
            kind=kind,
            nodes=nodes,
            end=end)
    return result


def parse_nodes(string):
    """ Nodes or None. """
    result = []
    if string.item() != ")":
        while True:
            node = parse_node(string)
            if node is not None:
                result.append(node)
            else:
                result = None
                break
            if node.end == FOLLOWED_BY_END:
                break
    return result


# Words
# ============================================================================

# Type
# ----------------------------------------------------------------------------
Word = collections.namedtuple("Word", ["text", "level", "kind"])

# Constants
# ----------------------------------------------------------------------------
WORD_TOKEN = 1
WORD_SEPARATOR = 2
WORD_OPERATOR = 3
WORD_OPEN = 4
WORD_CLOSE = 5


# Line
# ============================================================================

# Type
# ----------------------------------------------------------------------------
Line = collections.namedtuple("Line", ["indent", "words"])


# Methods
# ----------------------------------------------------------------------------

def line_image(line):
    """ Image of line as string. """
    result = "  " * line.indent
    words = line.words
    i = 0
    first = 0
    last = len(words) - 1
    while i <= last:
        word = words[i]
        if word.kind == WORD_OPERATOR and i > first:
            result += " "
        result += word.text
        if word.kind == WORD_OPERATOR and i < last:
            result += " "
        if word.kind == WORD_SEPARATOR and i < last:
            result += " "
        i += 1
    return result


# Lines
# ============================================================================

def lines_image(lines):
    """ Image of lines as string. """
    result = ""
    for line in lines:
        result += line_image(line)
        result += "\n"
    return result


def append_words_as_line(result, words, indent):
    """ Helper. """
    if len(words) > 0:
        line = Line(indent, words)
        result.append(line)


def splitted_at_separator(line):
    """ Split line at separators kept at the end of each lines. """
    if len(line.words) > 0:
        indent = line.indent
        words = line.words
        level = words[0].level
        result = []
        line_words = []
        i = 0
        last = len(words) - 1
        while i <= last:
            word = words[i]
            line_words.append(word)
            if word.kind == WORD_SEPARATOR and word.level == level:
                line = Line(indent, line_words)
                result.append(line)
                line_words = []
            i += 1
        append_words_as_line(result, line_words, indent)
    else:
        result = [line]
    return result


def splitted_at_operator(line):
    """ Split line at operators kept at the start of each lines. """
    if len(line.words) > 0:
        indent = line.indent
        words = line.words
        level = words[0].level
        result = []
        line_words = []
        i = 0
        last = len(words) - 1
        while i <= last:
            word = words[i]
            if word.kind == WORD_OPERATOR and word.level == level:
                append_words_as_line(result, line_words, indent)
                line_words = []
            line_words.append(word)
            i += 1
        append_words_as_line(result, line_words, indent)
    else:
        result = [line]
    return result


def indented_on_next_level(line):
    """ Split line with indent on next level. """

    words = line.words
    if len(line.words) > 0:
        i = 0
        last = len(words) - 1
        level = words[0].level
        result = []

        def part(cond, indent):
            """ New line with `indent` with words while `cond`.

            `cond` is whether or not, `word.level == level`.

            """
            nonlocal words, i, last, level, result
            line_words = []
            while i <= last:
                word = words[i]
                if (word.level == level) != cond:
                    break
                line_words.append(word)
                i += 1
            append_words_as_line(result, line_words, indent)

        indent = line.indent
        while i <= last:
            part(True, indent)
            part(False, indent+1)
    else:
        result = [line]
    return result


def format_lines(lines):
    """ Split and indent lines to fit max width. """
    changed = True
    result = lines
    while changed:
        lines = result
        result = []
        changed = False
        for line in lines:
            if len(line_image(line)) <= LINE_WIDTH:
                result.append(line)
            else:
                sublines = splitted_at_separator(line)
                if len(sublines) > 1:
                    result += sublines
                    changed = True
                else:
                    sublines = splitted_at_operator(line)
                    if len(sublines) > 1:
                        result += sublines
                        changed = True
                    else:
                        sublines = indented_on_next_level(line)
                        if len(sublines) > 1:
                            result += sublines
                            changed = True
                        else:
                            result.append(line)
    return result


# Node Image as Word List
# ============================================================================

def append_end(node, level, acc):
    """ Helper. """
    if node.end == FOLLOWED_BY_SEMI_COLON:
        acc.append(Word(";", level, WORD_SEPARATOR))
    elif node.end == FOLLOWED_BY_COMMA:
        acc.append(Word(",", level, WORD_SEPARATOR))
    elif node.end == FOLLOWED_BY_ARROW:
        acc.append(Word("->", level, WORD_OPERATOR))
    elif node.end == FOLLOWED_BY_END:
        pass


def node_image(node, level, acc, with_end=True):
    """ Image of a node as word list. """
    result = acc
    if not simplified_image(node, level, result):
        result.append(Word(node.token, level, WORD_TOKEN))
        if node.nodes is not None:
            result.append(Word("(", level, WORD_OPEN))
            for subnode in node.nodes:
                result = node_image(subnode, level+1, result)
            result.append(Word(")", level, WORD_CLOSE))
    if with_end:
        append_end(node, level, result)
    return result


# Node Image as a List of one Line
# ============================================================================

def node_lines_image(node):
    """ Image of node as lines. """
    words = []
    words = node_image(node, 0, words)
    result = [Line(0, words)]
    return result


# Node Image Simplification
# ============================================================================

# Constants
# ----------------------------------------------------------------------------

NAME_AS_OPERATOR = {
    "mul_int_int": "*",
    "add_int_int": "+",
    "sub_int_int": "*",
}


# Helper
# ----------------------------------------------------------------------------

def is_int(string):
    """ Helper. """
    try:
        int(string)
        result = True
    except ValueError:
        result = False
    return result


# Methods
# ----------------------------------------------------------------------------

def s2eintinf_simplified_image(node, level, acc):
    """ S2Eintinf(number) --> number. """
    result = False
    if node.token == "S2Eintinf":
        if node.nodes is not None and len(node.nodes) == 1:
            subnode = node.nodes[0]
            if subnode.nodes is None:
                acc.append(Word(subnode.token, level, WORD_TOKEN))
                result = True
    return result


def s2ecst_simplified_image(node, level, acc):
    """ S2Ecst(name) --> name | symbol. """
    result = False
    if node.token == "S2Ecst":
        if node.nodes is not None and len(node.nodes) == 1:
            subnode = node.nodes[0]
            if subnode.nodes is None:
                token = subnode.token
                if token in NAME_AS_OPERATOR:
                    operator = NAME_AS_OPERATOR[token]
                    acc.append(Word(operator, level, WORD_OPERATOR))
                else:
                    acc.append(Word(token, level, WORD_TOKEN))
                result = True
    return result


def d2s2evar_simplified_image(node, level, acc):
    """ (D2|S2)Evar(name(number)) --> name. """
    result = False
    if (node.token == "D2Evar") or (node.token == "S2Evar"):
        if node.nodes is not None and len(node.nodes) == 1:
            node = node.nodes[0]
            if node.nodes is not None and len(node.nodes) == 1:
                subnode = node.nodes[0]
                if subnode.nodes is None and is_int(subnode.token):
                    acc.append(Word(node.token, level, WORD_TOKEN))
                    result = True
    return result


def s2eapp_simplified_image(node, level, acc):
    """ S2Eapp(name|sym; arg1, arg2) --> name(arg1, arg2) | (arg1 sym arg2).

    """
    result = False
    if node.token == "S2Eapp":
        if node.nodes is not None and len(node.nodes) == 3:
            node1 = node.nodes[0]
            node2 = node.nodes[1]
            node3 = node.nodes[2]
            if (node1.end == FOLLOWED_BY_SEMI_COLON
                    and node2.end == FOLLOWED_BY_COMMA
                    and node3.end == FOLLOWED_BY_END):
                image1 = node_image(node1, level+1, [], False)
                image2 = node_image(node2, level+1, [], False)
                image3 = node_image(node3, level+1, [], False)
                if len(image1) == 1 and is_symbol_char(image1[0].text[0]):
                    acc.append(Word("(", level, WORD_OPEN))
                    acc += image2
                    acc.append(Word(image1[0].text, level+1, WORD_OPERATOR))
                    acc += image3
                    acc.append(Word(")", level, WORD_CLOSE))
                else:
                    acc += image1
                    acc.append(Word("(", level, WORD_OPEN))
                    acc += image2
                    acc.append(Word(",", level+1, WORD_SEPARATOR))
                    acc += image3
                    acc.append(Word(")", level, WORD_CLOSE))
                result = True
    return result


def s2eeqeq_simplified_image(node, level, acc):
    """ S2Eeqeq(arg1, arg2) --> (arg1 == arg2). """
    result = False
    if node.token == "S2Eeqeq":
        if node.nodes is not None and len(node.nodes) == 2:
            node1 = node.nodes[0]
            node2 = node.nodes[1]
            if (node1.end == FOLLOWED_BY_SEMI_COLON
                    and node2.end == FOLLOWED_BY_END):
                image1 = node_image(node1, level+1, [], False)
                image2 = node_image(node2, level+1, [], False)
                acc.append(Word("(", level, WORD_OPEN))
                acc += image1
                acc.append(Word("==", level+1, WORD_OPERATOR))
                acc += image2
                acc.append(Word(")", level, WORD_CLOSE))
                result = True
    return result


def c3nstrprop_simplified_image(node, level, acc):
    """ C3NSTRprop(C3NSTRprop(); expression) --> expression. """
    result = False
    if node.token == "C3NSTRprop":
        nodes = node.nodes
        if nodes is not None and len(nodes) == 2:
            node1 = nodes[0]
            if (node1.token == "C3TKmain"
                    and node1.nodes is not None
                    and len(node1.nodes) == 0):
                node2 = nodes[1]
                node_image(node2, level, acc)
                result = True
    return result


def name_simplified_image(node, level, acc):
    """ name(number) --> name. """
    result = False
    if node.kind == KIND_NAME:
        if node.nodes is not None and len(node.nodes) == 1:
            subnode = node.nodes[0]
            if subnode.nodes is None and is_int(subnode.token):
                acc.append(Word(node.token, level, WORD_TOKEN))
                result = True
    return result


# Main
# ----------------------------------------------------------------------------

SIMPLIFIED_IMAGE_METHODS = [
    s2eintinf_simplified_image,
    s2ecst_simplified_image,
    d2s2evar_simplified_image,
    s2eapp_simplified_image,
    s2eeqeq_simplified_image,
    c3nstrprop_simplified_image,
    name_simplified_image,
]


def simplified_image(node, level, acc):
    """ Simplified node image. """
    result = False
    if SIMPLIFY:
        for method in SIMPLIFIED_IMAGE_METHODS:
            result = result or method(node, level, acc)
    return result


# Main
# ============================================================================

def is_root_node(node):
    """ An D2/S2/C3 node follow by end. """
    result = (
        node is not None
        and node.kind == KIND_D2S2C3
        and node.end == FOLLOWED_BY_END)
    return result


def folded(string):
    """ Fold funny things. """
    result = ""
    trees = []
    string = String(string)
    while string.has_item():
        string.push()
        tree = parse_node(string)
        if is_root_node(tree):
            string.unpush()
            result += "…"
            trees.append(tree)
        else:
            string.pop()
            result += string.item()
            string.consume()
    result += "\n"
    for tree in trees:
        lines = node_lines_image(tree)
        lines = format_lines(lines)
        result += lines_image(lines)
    return result


def main():
    """ Main. """
    for line in sys.stdin:
        line = line.strip()
        if is_message_with_location(line):
            message = parse_message_with_location(line)
            text = folded(message.text)
            if LOC_WITH_COLUMN:
                output = (
                    "%s:%i:%i: %s"
                    % (message.path,
                       message.line,
                       message.col,
                       text))
            else:
                output = (
                    "%s:%i: %s"
                    % (message.path,
                       message.line,
                       text))
            print(output)
        else:
            print(line)


if __name__ == "__main__":
    main()
