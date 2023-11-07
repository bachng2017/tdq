#!/usr/bin/env python3

import os,sys,argparse,configparser,csv
import tdclient
from prettytable import PrettyTable
from tdq import _version
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.shortcuts import prompt
from prompt_toolkit import PromptSession
from prompt_toolkit.history import FileHistory
import re
from tdq import _version
from pygments.lexers.sql import SqlLexer
from prompt_toolkit.lexers import PygmentsLexer


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

        @self.kb.add('enter')
        def _(event):
            # if ';' in event.current_buffer.text or '\G' in event.current_buffer.text:
            self.process_newline(event.current_buffer.text, event.current_buffer)

        # read from config file
        config_path = os.path.expanduser(CONFIG_FILE)
        self.config = configparser.ConfigParser()

        if os.path.exists(config_path):
            self.config.read(config_path)

        if 'account' not in self.config:
            self.config['account'] = {}
        if 'database' not in self.config['account']: self.config['account']['database'] = ''
        if 'apikey' not in self.config['account']: self.config['account']['endpoint'] = ''
        if 'endpoint' not in self.config['account']: self.config['account']['endpoint'] = ''

        self.apikey = os.getenv("TD_API_KEY") or self.config['account']['apikey']
        self.endpoint = ARGS.endpoint or os.getenv("TD_SERVER") or self.config['account']['endpoint']
        self.database = ARGS.database or self.config['account']['database']
        self.prompt = f"TdQuery({self.database}) > "


    def do_xxx(self, args):
        print(f"this is method xxx, called with {args}")

    def do_quit(self, args):
        self.exit_loop = True
        print("Bye.")


    def do_exit(self, args):
        self.do_quit(args)


    def do_display(self, args):
        if args in ['','vertical','horizontal','csv']:
            self.display_mode = args
        mode = "<auto>"
        if self.display_mode != '': mode = self.display_mode
        print(f"current display mode is {mode}")

    def do_use(self, args):
        if args != '':
            self.database = args
            self.prompt = f"TdQuery({self.database}) > "
        print(f"current database is {self.database}")


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

        if _mode == 'vertical':
            formatted = []
            max_field_width = max([len(x) for x in table._field_names])
            for row_i, row in enumerate(table._rows):
                formatted.append('*************************** %i. row ***************************' % (row_i + 1, ))
                for i, field in enumerate(table._field_names):
                    formatted.append("%s: %s" % (field.rjust(max_field_width), row[i]))
            print('\n'.join(formatted),file=self.stdout)

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


    def process_newline(self, input_str, input_buffer = None):
        """ Check the current input buffer for every <newline> event (Enter pressed)
            Buffer could include multi SQL queries
        """

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
        r = re.match(r'.*(\w+).*(;|\\G|\s)+$',input_str,re.DOTALL)
        if r:
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
        # simply split the input. Need to care about the ; char is inside a string
        cmd_list = re.findall(r'\w.+?;|\w.+?\\G|\w.+?$',cmds,re.DOTALL)

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
                        print(error, file = sys.stderr)
                        print(self.render_error(query, error), file = sys.stderr)
                    else:
                        result = PrettyTable(list(map(lambda x : x[0],job.result_schema)))
                        result.align = "l"
                        row_num = 0
                        for row in job.result():
                            result.add_row(row)
                            row_num += 1

                        self.print_table(result, mode)
                        print(f"({row_num} row{'s'[:row_num^1]})\n")
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
                        key_bindings=self.kb,
                        multiline=True,
                        prompt_continuation=self.prompt_continuation)
                if self.mode == 'file':
                    result = self.stdin.readline().rstrip()
                    self.process_newline(result)
            except KeyboardInterrupt: continue
            except EOFError: break
            else:
                cmd = result.split(' ')[0].strip()

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
    shell.cmdloop()


# main
if __name__ == '__main__':
    main()
