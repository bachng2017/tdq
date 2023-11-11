#!/usr/bin/env python3

import os, sys,re, argparse, csv, configparser
import tdclient, sqlparse

from prettytable import PrettyTable
from tdq import _version,utils
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.shortcuts import prompt
from prompt_toolkit import PromptSession
from prompt_toolkit.history import FileHistory
from tdq import _version
from pygments.lexers.sql import SqlLexer
from prompt_toolkit.lexers import PygmentsLexer
from prompt_toolkit.auto_suggest import AutoSuggestFromHistory
from prompt_toolkit.filters import Condition

PROG = "tdq"
# config file (created by td client)
CONFIG_FILE = '~/.td/td.conf'
TDQ_HISTORY = '~/.tdqhistory'
CSV_OUTPUT_FORMAT = 'CSV_HEADER'



class TDQuery:
    """ Treasure Data Query client
    """

    def __init__(self,mode, stdin = sys.stdin, stdout = sys.stdout):
        self.mode = mode # prompt or file

        self.display_mode = ''  # vertical/horizontal/csv. Empty is automatic

        self.stdin = stdin
        self.stdout = stdout

        self.engine = "presto"

        self.exec_query = True
        self.exec_command = False
        self.exit_loop = False

        self.session = PromptSession(
            history=FileHistory(os.path.expanduser(TDQ_HISTORY)),
            lexer=PygmentsLexer(SqlLexer))


        self.kb = KeyBindings()

        @self.kb.add('c-c')
        def _(event):
            self.exec_query = False
            self.exec_command = False
            event.current_buffer.validate_and_handle()


        @self.kb.add('c-a')
        def _(event):
            b = event.current_buffer
            col = b.document.cursor_position_col
            relative_begin_index = b.document.get_start_of_line_position()
            if col == 0:
                b.cursor_up()
            else:
                b.cursor_left(count=abs(relative_begin_index))


        @self.kb.add('c-e')
        def _(event):
            b = event.current_buffer
            complete_state = b.complete_state
            relative_end_index = b.document.get_end_of_line_position()

            if b.suggestion is not None and b.document.is_cursor_at_the_end:
                suggestion = b.suggestion
                b.insert_text(suggestion.text)
                return

            if relative_end_index == 0:
                b.cursor_down()
                b.cursor_right(b.document.get_end_of_line_position())
            else:
                b.cursor_right(count=abs(relative_end_index))


        @self.kb.add('c-j')
        def _(event):
            event.current_buffer.newline()

        @self.kb.add('c-b')
        def _(event):
            b = event.current_buffer
            col = b.document.cursor_position_col
            if col == 0:
                row = b.document.cursor_position_row
                if row != 0:
                    b.cursor_up()
                    relative_end_index = b.document.get_end_of_line_position()
                    b.cursor_right(count=abs(relative_end_index))
            else:
                b.cursor_left()

        @self.kb.add('c-f')
        def _(event):
            b = event.current_buffer
            relative_end_index = b.document.get_end_of_line_position()
            if relative_end_index == 0:
                if not b.document.is_cursor_at_the_end:
                    relative_start_index = b.document.get_start_of_line_position()
                    b.cursor_down()
                    b.cursor_left(-relative_start_index)
            else:
                b.cursor_right()


        @self.kb.add('enter')
        def _(event):
            # if ';' in event.current_buffer.text or '\G' in event.current_buffer.text:
            self.process_enter(event.current_buffer.text, event.current_buffer)

        # read from config file
        config_path = os.path.expanduser(CONFIG_FILE)
        self.config = configparser.ConfigParser()

        if os.path.exists(config_path):
            self.config.read(config_path)

        if 'account' not in self.config:
            self.config['account'] = {}
        if 'database' not in self.config['account']: self.config['account']['database'] = ''
        if 'apikey' not in self.config['account']: self.config['account']['apikey'] = ''
        if 'endpoint' not in self.config['account']: self.config['account']['endpoint'] = ''
        if 'engine' not in self.config['account']: self.config['account']['engine'] = ''

        self.apikey = os.getenv("TD_API_KEY") or self.config['account']['apikey']
        self.endpoint = ARGS.endpoint or os.getenv("TD_SERVER") or self.config['account']['endpoint']
        self.database = ARGS.database or self.config['account']['database']
        self.engine = ARGS.database or self.config['account']['engine'] or self.engine

        self.prompt = f"TdQuery({self.database}) > "


    def do_help(self, args):
        """ help command
        """
        cmd_list = sorted(list(filter(lambda x: x.startswith('do_'), dir(self))))
        if args == '':
            col_num = 10
            print("Internal commands (type help <topic>):")
            print("======================================\n")

            for i in range(0, len(cmd_list), col_num):
                print(' '.join(f"{s[3:]:10}" for s in cmd_list[i:i+col_num]))
            print("\n")
        else:
            if hasattr(self,'help_' + args):
                getattr(self,'help_' + args)()
            else:
                print("Unknown command")


    def help_help(self):
        print("print out all availabel commands")


    def do_engine(self, args):
        if not args in ["presto", "hive", ""]:
            print("Invalid option")
            return
        if args != "":
            self.engine = args

        print(f"Current engine is {self.engine}")


    def help_engine(self):
        print("Set current SQL engine. Value should be presto(default) or hive")


    def do_quit(self, args):
        self.exit_loop = True
        print("Bye.")

    def help_quit(self):
        print("Quit the shell")


    def do_exit(self, args):
        self.do_quit(args)

    def help_exit(self):
        self.help_quit()


    def do_display(self, args):
        """ display command
        """
        if not args in ['','vertical','horizontal','csv']:
            print("Invalid option")
            return
        mode = "<auto>"
        if args in ['horizontal','vertical','csv']:
            self.display_mode = args
        print(f"current display mode is {mode}")


    def help_display(self):
        """ help for display command
        """
        print("change output mode. Usage: display <mode>")
        print("Valid mode is horizontal(default), vertical, csv or empty string")


    def do_use(self, args):
        """ Change the current database
        """
        if args != '':
            self.database = args
            self.prompt = f"TdQuery({self.database}) > "
        print(f"current database is {self.database}")

    def help_use(self):
        """ help for use command
        """
        print("Change the current database. Usage: use <sample_database>")




    def print_table(self, table, mode = None):
        """ Given a PrettyTable table instance, format each row vertically (similar to mysql's \G display)
            mode: overwrite client display mode if defined
        """
        if self.display_mode == '':
            _mode = mode
        else:
            _mode = self.display_mode
        output_format = ARGS.output_format or CSV_OUTPUT_FORMAT

        if _mode == 'horizontal':
            print(table,file=self.stdout)

        # print the table in vertical direction
        if _mode == 'vertical':
            formatted = []
            max_field_width = max([len(x) for x in table._field_names])
            for row_i, row in enumerate(table._rows):
                formatted.append('-[ RECORD %i ]' % (row_i + 1, ))
                for i, field in enumerate(table._field_names):
                    formatted.append("%s | %s" % (field.ljust(max_field_width), row[i]))
            print('\n'.join(formatted),file=self.stdout)

        # print the table in CSV format to the current stdout (could be a file)
        if _mode == 'csv':
            if output_format == "CSV":
                writer = csv.writer(self.stdout,quoting=csv.QUOTE_ALL)
                for row in table._rows:
                    writer.writerow(row)
            if output_format == "CSV_HEADER":
                writer = csv.writer(self.stdout,quoting=csv.QUOTE_ALL)
                writer.writerow(table._field_names)
                for row in table._rows:
                    writer.writerow(row)
            if output_format == "CSV_UNQUOTED":
                writer = csv.writer(self.stdout,quoting=csv.QUOTE_NONE)
                for row in table._rows:
                    writer.writerow(row)
            if output_format == "CSV_HEADER_UNQUOTED":
                writer = csv.writer(self.stdout,quoting=csv.QUOTE_NONE)
                writer.writerow(table._field_names)
                for row in table._rows:
                    writer.writerow(row)


    def render_error(self, query, error):
        """ rendering an query from erro info
            Return a rendered string with ANSI color code
        """
        CRED = '\033[91m'
        CEND = '\033[0m'
        r = re.match(r"Query .* failed: line (\d+):(\d+): ", error)

        row = int(r.group(1))
        col = int(r.group(2))

        tmp = query.split("\n")
        target = tmp[row - 1]
        if col - 1 >= len(target):
            tmp[row-1] = target + CRED + " <EOF>" + CEND
        else:
            tmp[row-1] = target[:col-1] + CRED + target[col-1:] + CEND
        return "\n".join(tmp)



    def prompt_continuation(self, width, line_number, is_soft_wrap):
        return '.' * (width - 1) + ' '


    def process_enter(self, input_str, input_buffer = None):
        """ Check the current input buffer for every <newline> event (Enter pressed)
            Buffer could include multi SQL queries
        """
        # print(f"input_str = {input_str}")

        # only enter pressed, continue input
        if input_str.strip() == "":
            self.exec_query = False
            if input_buffer: input_buffer.validate_and_handle()
            return False

        # internal command process 
        r = re.match("(\w+) *(.*)$", input_str)
        if r:
            method = 'do_' + r.group(1)
            if hasattr(self, method):
                self.exec_query = False
                self.exec_command = True
                if input_buffer: input_buffer.validate_and_handle()
                return True

        # finish input and exec query
        # r = re.match(r'.*(\w+).*(;|\\G|\s)+$',input_str,re.DOTALL)
        # if r:
        tmp = utils.split_sql(input_str)
        if len(tmp) > 1 or tmp[0].endswith(";") or tmp[0].endswith("\G"):
            self.exec_query = True
            if input_buffer: input_buffer.validate_and_handle()
            return True

        if input_buffer: input_buffer.newline()
        return False


    def process_command(self, cmd_str):
        """ process internal command
        """
        r = re.match(r"(\w+) *(\w*?)(?:;|\\G)*$", cmd_str)
        method = 'do_' + r.group(1)
        args = r.group(2)
        getattr(self, method)(args)


    def process_input(self, cmds, stdout = sys.stdout):
        """ process user input and write results to stdout
        """
        cmd_list = utils.split_sql(cmds)

        for cmd in cmd_list:
            with tdclient.Client(apikey=self.apikey,endpoint=self.endpoint) as client:

                # display mode for this command
                # if the client's display mode is not define
                # the mode will be set by the last char of the command
                mode = 'horizontal'
                if self.display_mode:
                    mode = self.display_mode
                else:
                    if cmd[-2:] == '\G':
                        mode = 'vertical'

                query_str = cmd.rstrip("\\G; \n")
                if query_str == '': continue

                # execute the query to remote server
                try:
                    job = client.query(self.database, query_str, type="presto")
                    # sleep until job's finish
                    job.wait()
                    job_detail = client.api.show_job(job.id)

                    if job.error():
                        query = job_detail['query']
                        error = job_detail['debug']['stderr']
                        # print("Unknown query or query error", file=sys.stderr)
                        print(error, file = sys.stderr,end="")
                        print(self.render_error(query, error), file = sys.stderr)
                        print()
                    else:
                        result = PrettyTable(list(map(lambda x : x[0],job.result_schema)))
                        result.align = "l"
                        row_num = 0
                        for row in job.result():
                            result.add_row(row)
                            row_num += 1

                        self.print_table(result, mode)
                        print(f"({row_num} row{'s'[:row_num^1]})\n")
                except KeyboardInterrupt:
                    print("Query aborted by user")
                except Exception as e:
                    print(e, file=sys.stderr)



    def cmdloop(self):
        """ Receive user's input
        """
        if self.mode not in ['prompt','file']:
            print("invalid mode. Should be prompt or file")
            return

        while True:
            self.exec_query = True
            self.exec_command = False
            self.exit_loop = False
            try:
                if self.mode == 'prompt':
                    result = self.session.prompt(
                        self.prompt,
                        auto_suggest=AutoSuggestFromHistory(),
                        key_bindings=self.kb,
                        multiline=True,
                        prompt_continuation=self.prompt_continuation)
                if self.mode == 'file':
                    result = self.stdin.readline().rstrip()
                    result = self.stdin.readline().rstrip()
                    self.process_enter(result)
            except KeyboardInterrupt: continue
            except EOFError: break
            else:
                if self.exec_command:
                    self.process_command(result)
                if self.exit_loop: break
                if self.exec_query:
                    self.process_input(result, self.stdout)



# global
# define parser
parser = argparse.ArgumentParser(PROG)
parser.add_argument(
    "-f","--file",
    type=str,
    help="execute statements from file and exit"
)
parser.add_argument(
    "-o","--output",
    type=str,
    help="write output to file instead of stdoutput"
)
parser.add_argument(
    "--output-format",
    type=str,
    choices = ["CSV","CSV_HEADER","CSV_UNQUOTED","CSV_HEADER_UNQUOTED"],
    help="format the CSV output. Should be one of CSV,CSV_HEADER,CSV_UNQUOTED,CSV_HEADER_UNQUOTED"
)
parser.add_argument(
    "-d","--database",
    type=str,
    help="use database"
)
parser.add_argument(
    "-e","--endpoint",
    type=str,
    default="https://api.treasuredata.co.jp/",
    help="TreasureData endpoint (default: https://api.treasuredata.co.jp/)"
)
parser.add_argument(
    "-g","--engine",
    type=str,
    default="presto",
    choices = ["presto","hive"],
    help="SQL query engine. Should be presto or hive"
)
parser.add_argument(
    "-v","--version",
    action="version",
    version=_version.__version__
)

# parsing program argument
ARGS = parser.parse_args()



# main program
def main():
    if ARGS.output:
        stdout = open(ARGS.output,'w')
    else:
        stdout = sys.stdout

    shell = None
    if ARGS.file:
        stdin = open(ARGS.file,'r')
        shell = TDQuery('file',stdin,stdout)
    else:
        stdin = sys.stdin
        shell = TDQuery('prompt',stdin,stdout)

    print(f"*** TDQuery shell. Ctrl-D to quit")
    print(f"*** endpoint = {shell.endpoint}")
    print(f"*** apikey(last 3 digits) = ...{shell.apikey[-3:]}")
    print()
    shell.cmdloop()


# main
if __name__ == '__main__':
    main()
