#!/usr/bin/python3

import re
from abc import ABCMeta, abstractmethod

class Property(object):
    __metaclass__ = ABCMeta

    def __init__(self):
        self.values = []

    def serialize(self):
        s = self.prop_ident
        for prop_value in self.values:
            s += "[{}]".format(prop_value)
        return s

    @classmethod
    @abstractmethod
    def deserialize(cls, data):
        # Skip any leading whitespace.
        data = data.lstrip()
        if not data.startswith(cls.prop_ident):
            raise ValueError("Unexpected property identifier.")

        # Skip the property identifier and trailing whitespace.
        data = data[len(cls.prop_ident):].lstrip()

        # Match the PropValue part.
        regex = '|'.join([Number.regex, SimpleText.regex])
        m = re.match('\[({})\]'.format(regex), data)
        if not m or m.lastindex != 1:
            raise ValueError("Invalid property value.")

        return m.group(1)

    def __str__(self):
        return self.serialize()

class AP(Property):
    prop_ident = "AP"

    def __init__(self, name, version):
        super().__init__()
        self.values.append(Compose((name, version)))

class CA(Property):
    prop_ident = "CA"

    def __init__(self, charset="ISO-8859-1"):
        super().__init__()
        self.values.append(SimpleText(charset))

    @classmethod
    def deserialize(cls, data):
        charset = super().deserialize(data)
        return CA(charset)

class GM(Property):
    prop_ident = "GM"

    def __init__(self, number=1):
        super().__init__()
        self._validate_number(number)
        self.values.append(number)

    @staticmethod
    def _validate_number(number):
        if not 1 <= number <= 40:
            raise ValueError("Unknown game type '{}'.".format(number))

    @classmethod
    def deserialize(cls, data):
        number = int(super().deserialize(data))
        return GM(number)

class FF(Property):
    prop_ident = "FF"

    def __init__(self, number=1):
        super().__init__()
        self._validate_number(number)
        self.values.append(number)

    @staticmethod
    def _validate_number(number):
        if not 1 <= number <= 4:
            raise ValueError("Unknown file format '{}'.".format(number))

    @classmethod
    def deserialize(cls, data):
        number = int(super().deserialize(data))
        return FF(number)

class RU(Property):
    prop_ident = "RU"

    def __init__(self, text):
        super().__init__()
        self.values.append(text)

class ST(Property):
    prop_ident = "ST"

    def __init__(self, number):
        super().__init__()
        self._validate_number(number)
        self.values.append(number)

    @staticmethod
    def _validate_number(number):
        if not 0 <= number <= 3:
            raise ValueError("Unknown style '{}'.".format(number))

class SZ(Property):
    prop_ident = "SZ"

    def __init__(self, o):
        super().__init__()
        if isinstance(o, Compose):
            if o.values[0] == o.values[1]:
                raise ValueError("Square boards must not be defined using the compose type.")
            self.values.append(o)
        else:
            self.values.append(Number(o))

class Compose(object):
    def __init__(self, arg):
        if isinstance(arg, Compose):
            self.values = arg.values
        else:
            if len(arg) != 2:
                raise ValueError("Compose expects 2 elements.")
            self.values = [arg[0], arg[1]]

        # Convert to simpletext with compose = True to ensure proper
        # handling of ':' characters within SimpleText.
        if isinstance(self.values[0], SimpleText):
            self.values[0] = SimpleText(self.values[0], compose=True)

        if isinstance(self.values[1], SimpleText):
            self.values[1] = SimpleText(self.values[1], compose=True)

    def __str__(self):
        return self.serialize()

    def serialize(self):
        return "{}:{}".format(self.values[0], self.values[1])

class Number(object):
    regex = r"[+-]?\d+"

    def __init__(self, o):
        if isinstance(o, Number):
            self.value = o.value
        elif isinstance(o, str):
            self.value = int(o)
        else:
            self.value = o

    def __str__(self):
        return str(self.value)

class Text(object):
    """3.2. Text

       Text is a formatted text. White spaces other than linebreaks are
       converted to space (e.g. no tab, vertical tab, ..).

       Formatting:
       Soft line break:  linebreaks preceded by a "\" (soft linebreaks are
                         converted to "", i.e. they are removed)
       Hard line breaks: any other linebreaks encountered

       Attention: a single linebreak is represented differently on different
       systems, e.g. "LFCR" for DOS, "LF" on Unix. An application should be
       able to deal with following linebreaks: LF, CR, LFCR, CRLF.
       Applications must be able to handle Texts of any size. The text should
       be displayed the way it is, though long lines may be word-wrapped, if
       they don't fit the display.

       Escaping: "\" is the escape character. Any char following "\" is
       inserted verbatim (exception: whitespaces still have to be converted to
       space!). Following chars have to be escaped, when used in Text: "]", "\"
       and ":" (only if used in compose data type).
 
       Encoding: texts can be encoded in different charsets. See CA property."""

    def __init__(self, o, encoding="ISO-8859-1"):
        self._encoding = encoding
        if isinstance(o, Text):
            self.data  = o._data
        else:
            self._data = self.encode(o, encoding)

    @property
    def data(self):
        return self._data

    @staticmethod
    def encode(s, encoding="ISO-8859-1", compose=False):
        # Let splitlines() handle different unicode based line breaks.
        # This avoids having to enumerate unicode line breaks explicitly.
        need_escape = ":]"[not compose:]
        linebreak   = lambda c: len(c.splitlines()[0]) == 0
        whitespace  = lambda c: re.match('\s', c, re.UNICODE) is not None
        escape      = False
        text        = ""
        for i, c in enumerate(s):
            if not escape and c == '\\':
                escape = True
            elif not escape and c in need_escape:
                raise ValueError("Unescaped use of '{}'.".format(c))
            elif escape and linebreak(c):
                escape = False
            elif whitespace(c) and not linebreak(c):
                escape = False
                text += ' '
            else:
                escape = False
                text += c

        # We have a trailing escape sequence, so we error out.
        if escape:
            raise ValueError("Unexpected escape sequence.")

        return text.encode(encoding)

class SimpleText(object):
    """3.3. SimpleText

       SimpleText is a simple string. Whitespaces other than space must be
       converted to space, i.e. there's no newline! Applications must be able
       to handle SimpleTexts of any size.

       Formatting: linebreaks preceded by a "\" are converted to "", i.e. they
       are removed (same as Text type).  All other linebreaks are converted to
       space (no newline on display!!).

       Escaping (same as Text type): "\" is the escape character. Any char
       following "\" is inserted verbatim (exception: whitespaces still have to
       be converted to space!). Following chars have to be escaped, when used
       in SimpleText: "]", "\" and ":" (only if used in compose data type).

       Encoding (same as Text type): SimpleTexts can be encoded in different
       charsets. See CA property."""

    # XXX: handle escape sequences and ':'
    regex = r'[^\]]*'

    def __init__(self, o, encoding=None, compose=False):
        if isinstance(o, SimpleText):
            if encoding is None: encoding = o._encoding
            self._data = o._data
        else:
            if encoding is None: encoding = "ISO-8859-1"
            self._data = self.encode(o, encoding, compose)
        self._encoding = encoding

    @property
    def data(self):
        return self._data

    def __str__(self):
        return str(self.data)

    @staticmethod
    def encode(s, encoding="ISO-8859-1", compose=False):
        # Let splitlines() handle different unicode based line breaks.
        # This avoids having to enumerate unicode line breaks explicitly.
        need_escape = ":]"[not compose:]
        linebreak   = lambda c: len(c.splitlines()[0]) == 0
        escape      = False
        text        = ""
        for i, c in enumerate(s):
            if not escape and c == '\\':
                escape = True
            elif not escape and c in need_escape:
                raise ValueError("Unescaped use of '{}'.".format(c))
            elif escape and linebreak(c):
                escape = False
            else:
                escape = False
                text += c

        # We have a trailing escape sequence, so we error out.
        if escape:
            raise ValueError("Unexpected escape sequence.")

        # Let the '\s' regex handle all whitespace in this encoding.
        text = re.sub('\s', ' ', text, flags=re.UNICODE)

        return text.encode(encoding)

if __name__ == '__main__':
    print(SZ(Compose((19, 18))))
    print(SZ(19))
    print(ST(2))
    print(AP("foo", "10.1"))
    print(CA.deserialize("CA[UTF-8]"))
    print(GM.deserialize(" GM[30]"))
    print(FF.deserialize("\tFF [3] "))
