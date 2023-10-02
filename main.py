# MaTeX: A LaTeX preprocessor
# Copyright 2023 OrthoPole. All rights reserved.


from typing import TextIO
from io import StringIO
import sys


VERSION = '1.3.0'
AUTHOR = 'OrthoPole'
YEAR = '2023'
DESCRIPTION = 'A LaTeX preprocessor'


# command line parser
class CommandLineParser:

    class UnknownShortcode(BaseException):
        def __init__(self, shortcode: str):
            self.shortcode = shortcode

    class CombinedShortcode(BaseException):
        def __init__(self, shortcode: str):
            self.shortcode = shortcode

    class UnknownOption(BaseException):
        def __init__(self, option: str):
            self.option = option

    class RepeatedOption(BaseException):
        def __init__(self, option: str):
            self.option = option

    def __init__(self):
        self._shortcodes = {}
        self._paralength = {}

    def add_shortcode(self, short: str, long: str) -> None:
        self._shortcodes[short] = long

    def set_paralength(self, long: str, length: int) -> None:
        self._paralength[long] = length

    def parse(self, args: list[str]) -> dict[str, list[str]]:
        d: dict = {'': []}
        mode: bool = False
        para: str = ''
        remain: int = 0
        for arg in args[1:]:
            if arg[0] == '-':
                if arg[1] == '-':
                    para = arg[2:]
                    if para in d:
                        raise self.RepeatedOption(para)
                    d[para] = []
                    if para in self._paralength:
                        mode = True
                        remain = self._paralength[para]
                    else:
                        raise self.UnknownOption(para)
                else:
                    for a in arg[1:]:
                        if a in self._shortcodes:
                            longcode = self._shortcodes[a]
                            if longcode in d:
                                raise self.RepeatedOption(longcode)
                            d[longcode] = []
                            if longcode in self._paralength and self._paralength[longcode] > 0:
                                if len(arg) == 2:
                                    para = longcode
                                    mode = True
                                    remain = self._paralength[para]
                                else:
                                    raise self.CombinedShortcode(a)
                        else:
                            raise self.UnknownShortcode(a)
            else:
                if mode:
                    d[para].append(arg)
                    remain -= 1
                    if remain == 0:
                        mode = False
                else:
                    d[''].append(arg)
        return d


# matex language compiler
class MatexCompiler:

    class _Reader:

        def __init__(self, input: TextIO):
            self._input = input
            self._seps = [0]

        def readline(self) -> tuple[str | None, str | None]:
            while self._input.readable():
                line = self._input.readline()
                if self.tell() > self._seps[-1]:
                    self._seps.append(self.tell())
                if line == '':
                    return None, None
                line = line.strip()
                if line == '':
                    continue
                if line[0] == '#':
                    continue
                try:
                    head, tail = line.split(' ', 1)
                except ValueError:
                    return line.upper(), ''
                return head.upper(), tail

        def tell(self) -> int:
            return self._input.tell()

        def seek(self, pos: int):
            self._input.seek(pos)

        def line(self) -> int:
            for i in range(len(self._seps)):
                if self._seps[i] >= self.tell():
                    return i
            return i

        def __iter__(self):
            return self

        def __next__(self) -> tuple[str, str, int]:
            head, tail = self.readline()
            if head is None:
                raise StopIteration
            line = self.line()
            return head, tail

    class _Executor:

        def __init__(self, compiler):
            self._compiler = compiler
            self._globals = {
                'upperlower': self._upperlower
            }

        def exec(self, code: str, variables: dict) -> bool:
            try:
                exec(code, self._globals, variables)
            except:
                return self._compiler._error(f'invalid python code')
            return True

        def eval(self, code: str, variables: dict) -> str:
            try:
                return eval(code, self._globals, variables)
            except:
                return self._compiler._error(f'invalid python code')

        @staticmethod
        def _upperlower(string: str) -> str:
            result = ''
            upper = True
            for char in string:
                if char == ' ':
                    result += char
                    continue
                elif char == char.upper() and not upper:
                    result += r'\normalsize '
                    upper = True
                elif char == char.lower() and upper:
                    result += r'\footnotesize '
                    upper = False
                result += char.upper()
            return result + r'\normalsize '

    _output: StringIO
    _input: _Reader
    _out_info: TextIO
    _out_error: TextIO
    _out_warning: TextIO

    def __init__(self, info: TextIO, error: TextIO, warning: TextIO):
        self._output = StringIO()
        self._out_info = info
        self._out_error = error
        self._out_warning = warning
        self._executor = self._Executor(self)

    def _print(self, *args, **kwargs):
        print(*args, **kwargs, file=self._output)

    def _info(self, *args, **kwargs):
        print(*args, **kwargs, file=self._out_info)

    def _error(self, *args, **kwargs):
        print(f'error: in line {self._input.line()}: ', end='', file=self._out_error)
        print(*args, **kwargs, file=self._out_error)
        return False

    def _warn(self, *args, **kwargs):
        print(f'warning: in line {self._input.line()}: ', end='', file=self._out_warning)
        print(*args, **kwargs, file=self._out_error)

    def finish(self, output: TextIO):
        self._output.seek(0)
        content = self._output.read()
        output.write(content)
        self._output.close()
        self._output = StringIO()

    def compile(self, input: TextIO, autocomment: bool = False) -> bool:
        self._input = self._Reader(input)
        head, tail = self._input.readline()
        if head is None:
            return self._error('version not specified')
        if head != 'VERSION':
            return self._error('version not specified at the head of file')
        try:
            version = int(tail)
        except ValueError:
            return self._error(f'version should be an integer (got "{tail}" instead)')
        if version == 1:
            return self._parse_v1(autocomment)
        else:
            return self._error(f'unknown version {version}')

    def _parse_v1(self, autocomment: bool = False, **kwargs) -> bool:

        if autocomment:
            self._print(f'% This file is automatically generated by MaTeX version {VERSION}.',
                        'Do not edit it manually.', sep=' ', end='\n\n')

        for head, tail in self._input:

            class UnmatchedBraces(BaseException):
                def __init__(self, index: int):
                    self.index = index

            class InvalidExpression(BaseException):
                def __init__(self, expression: str):
                    self.expression = expression

            def variable_replace(string: str, **kwargs) -> str | None:
                result = ''
                i = 0
                while i < len(string):
                    if string[i] == '%':
                        for j in range(i+1, len(string)):
                            if string[j] == '%':
                                break
                        if j == len(string):
                            raise UnmatchedBraces(i)
                        try:
                            result += str(self._executor.eval(string[i+1:j], kwargs))
                        except Exception:
                            raise InvalidExpression(string[i+1:j])
                        i = j + 1
                    else:
                        result += string[i]
                        i += 1
                return result

            try:
                tail = variable_replace(tail, **kwargs)
            except UnmatchedBraces as error:
                return self._error(f'unmatched `%` at column {error.index}')
            except InvalidExpression as error:
                return self._error(f'invalid expression `{error.expression}`')

            if head == 'DEF':
                mid = tail.upper().find(' TO BE ')
                if mid < 0:
                    return self._error('`TO BE` key words expected')
                macro = tail[:mid].strip()
                defin = tail[mid + 7:].strip()
                self._print(r'\def%s{%s}' % (macro, defin))

            elif head == 'CMD':
                mid1 = tail.upper().find(' TO BE ')
                mid2 = tail.upper().find(' OF ')
                mid3 = tail.upper().find(' DEFAULT ')
                if mid1 < 0:
                    return self._error('`TO BE` key words excepted')
                command = tail[:mid1].strip()
                if mid2 >= 0:
                    definition = tail[mid1+7:mid2].strip()
                    length = tail[mid2+4:mid3].strip()
                else:
                    definition = tail[mid1+7:].strip()
                    length = 0
                if mid3 >= 0:
                    if length == 0:
                        return self._error('cannot set default value for a command without parameters')
                    default = tail[mid3+9:]
                else:
                    default = None
                try:
                    length = int(length)
                except ValueError:
                    return self._error(f'parameter length should be an integer (got "{length}" instead)')
                if length < 0:
                    return self._error(f'parameter length should be non-negative (got {length} instead)')
                if default is None:
                    self._print(r'\newcommand{%s}[%d]{%s}' % (command, length, definition))
                else:
                    self._print(r'\newcommand{%s}[%d][%s]{%s}' % (command, length, default, definition))

            elif head == 'PAC':
                mid = tail.find(' OPTION ')
                if mid < 0:
                    package = tail.strip()
                    option = None
                else:
                    package = tail[:mid].strip()
                    option = tail[mid+8:].strip()
                if option is None:
                    self._print(r'\usepackage{%s}' % package)
                else:
                    self._print(r'\usepackage[%s]{%s}' % (option, package))

            elif head == 'ENV':
                mid1 = tail.upper().find(' PRE ')
                mid2 = tail.upper().find(' POST ')
                mid3 = tail.upper().find(' OF ')
                mid4 = tail.upper().find(' DEFAULT ')
                if mid1 < 0:
                    return self._error('`PRE` key word expected')
                if mid2 < 0:
                    return self._error('`POST` key word expected')
                environment = tail[:mid1].strip()
                pre = tail[mid1+5:mid2].strip()
                if mid3 < 0 and mid4 < 0:
                    post = tail[mid2+6:].strip()
                    length = 0
                    default = None
                elif mid3 >= 0 and mid4 < 0:
                    post = tail[mid2+6:mid3].strip()
                    length = tail[mid2+6:mid3].strip()
                    default = None
                elif mid3 < 0 and mid4 >= 0:
                    return self._error('cannot set default value for an environment without parameters')
                else:
                    post = tail[mid2+6:mid3].strip()
                    length = tail[mid3+4:mid4].strip()
                    default = tail[mid4+8:].strip()
                try:
                    length = int(length)
                except ValueError:
                    return self._error(f'parameter length should be an integer (got "{length}" instead)')
                if length < 0:
                    return self._error(f'parameter length should be non-negative (got {length} instead)')
                if default is None:
                    self._print(r'\newenvironment{%s}[%d]{%s}{%s}' % (environment, length, pre, post))
                else:
                    self._print(r'\newenvironment{%s}[%d][%s]{%s}{%s}' % (environment, length, default, pre, post))

            elif head == 'THM':
                mid1 = tail.upper().find(' COUNTER ')
                mid2 = tail.upper().find(' NAME ')
                mid3 = tail.upper().find(' UNDER ')
                mid4 = tail.upper().find(' STYLE ')
                if mid2 < 0:
                    return self._error('`NAME` key word expected')
                if mid1 < 0:
                    theorem = tail[:mid2].strip()
                    counter = None
                else:
                    theorem = tail[:mid1].strip()
                    counter = tail[mid1+9:mid2].strip()
                if mid3 < 0 and mid4 < 0:
                    name = tail[mid2+5:].strip()
                    under = None
                    style = None
                elif mid3 >= 0 and mid4 < 0:
                    name = tail[mid2+5:mid3].strip()
                    under = tail[mid3+6:].strip()
                    style = None
                elif mid3 < 0 and mid4 >= 0:
                    name = tail[mid2+5:mid4].strip()
                    under = None
                    style = tail[mid4+7:].strip()
                else:
                    name = tail[mid2+5:mid3].strip()
                    under = tail[mid3+6:mid4].strip()
                    style = tail[mid4+7:].strip()
                if style is not None:
                    self._print(r'\theoremstyle{%s}' % style, end='')
                if counter is None and under is None:
                    self._print(r'\newtheorem{%s}{%s}' % (theorem, name))
                elif counter is None and under is not None:
                    self._print(r'\newtheorem{%s}{%s}[%s]' % (theorem, name, under))
                elif counter is not None and under is None:
                    self._print(r'\newtheorem{%s}[%s]{%s}' % (theorem, name, counter))
                else:
                    self._print(r'\newtheorem{%s}[%s]{%s}[%s]' % (theorem, name, counter, under))

            elif head == 'RAW':
                self._print(tail.strip())

            elif head == 'COM':
                self._print('%', tail)

            elif head == 'FOR':
                mid = tail.upper().find(' IN ')
                if mid < 0:
                    return self._error('`IN` key word expected')
                variable = tail[:mid].strip()
                values = tail[mid+4:].strip()
                loop_start = self._input.tell()
                for value in values:
                    self._input.seek(loop_start)
                    kwargs[variable] = value
                    if not self._parse_v1(**kwargs):
                        return False

            elif head == 'END':
                return True

            else:
                return self._error(f'unexpected tag `{head}`')

        return True


if __name__ == '__main__':

    parser = CommandLineParser()
    parser.add_shortcode('o', 'output')
    parser.add_shortcode('v', 'version')
    parser.add_shortcode('c', 'auto-comment')
    parser.set_paralength('output', 1)
    parser.set_paralength('version', 0)
    parser.set_paralength('auto-comment', 0)

    try:
        result = parser.parse(sys.argv)
    except CommandLineParser.UnknownShortcode as error:
        print(f'error: unknown shortcode `-{error.shortcode}`', file=sys.stderr)
        sys.exit(-1)
    except CommandLineParser.CombinedShortcode as error:
        print(f'error: invalid combined shortcode `-{error.shortcode}', file=sys.stderr)
        sys.exit(-1)
    except CommandLineParser.UnknownOption as error:
        print(f'error: unknown option `--{error.option}`', file=sys.stderr)
        sys.exit(-1)
    except CommandLineParser.RepeatedOption as error:
        print(f'error: repeated option `--{error.option}`', file=sys.stderr)
        sys.exit(-1)

    if 'version' in result:
        if len(result) > 2:
            print(f'error: `--version` option is incompatible with other ones')
            sys.exit(-1)
        else:
            print(f'MaTeX {VERSION} - {DESCRIPTION}.')
            print(f'Copyright {YEAR} {AUTHOR}. All rights reserved.')
            sys.exit(0)

    if len(result['']) != 1:
        print(f'error: one and only one source file expected', file=sys.stderr)
        sys.exit(-1)

    source = result[''][0]

    if 'output' in result:
        target = result['output'][0]
    else:
        target = 'a.sty'
    if 'auto-comment' in result:
        autocomment = True
    else:
        autocomment = False

    try:
        source = open(source, 'r')
        target = open(target, 'w')
    except FileNotFoundError:
        print(f'error: file "{source}" not found')
        sys.exit(-1)
    except PermissionError:
        print(f'error: fail to write to file "{target}"')
        sys.exit(-1)

    compiler = MatexCompiler(sys.stdout, sys.stderr, sys.stderr)
    if compiler.compile(source, autocomment):
        compiler.finish(target)

    source.close()
    target.close()
