#!/usr/bin/env python3

import sys,os,cmd,re,readline,configparser,csv
import argparse
from prettytable import PrettyTable
import tdclient
from tdq import _version

histfile = os.path.expanduser('~/.tdq_history')
histfile_size = 1000

PROG = "tdq"
ARGS = {}


class TdQuery(cmd.Cmd):
    """Simple command processor example."""

    def __init__(self, stdin = None, output = None):
        # read config file (created by td client)
        config_file = os.path.expanduser('~/.td/td.conf')
        if os.path.exists(config_file):
            config = configparser.ConfigParser()
            config.read(config_file)
        else:
            config = {}
            config['account'] = {}
            config['account']['apikey'] = None
            config['account']['endpoint'] = None
            config['account']['database'] = None


        # use the module
        cmd.Cmd.__init__(self,stdin = stdin)
        cmd.Cmd.use_rawinput = not stdin

        # self initialize
        self.apikey = os.getenv("TD_API_KEY") or config['account']['apikey']
        self.endpoint = ARGS.endpoint or os.getenv("TD_SERVER") or config['account']['endpoint']
        self.database = ARGS.database or config['account']['database']

        self.display_mode = None # auto
        self.prompt = f"TdQuery({self.database}) > "
        self.prompt2 = f"--> "
        cmd.Cmd.prompt = self.prompt
        self.buffer = ''
        self.old_prompt = self.prompt
        self.output = output

        # debug
        # print(ARGS)


    def default(self, line):
        self.buffer += "\n"
        self.buffer += line

        # print(f"line = {line}")
        # print(f"buffer = {self.buffer}")

        # split buffer into SQL which terminated by ; or \\G
        r = re.findall(r'(.+?(?:;|\\G|$))+?',self.buffer,re.DOTALL)
        # print(r)

        # multiline input
        if len(r) > 0 and r[0][-1] not in [';','G']: 
           self.prompt = self.prompt2.rjust(len(self.prompt),' ')
        # could process more the one SQL
        else:
            self.execute_query(r)
            self.prompt = self.old_prompt


    def preloop(self):
        if readline and os.path.exists(histfile):
            readline.read_history_file(histfile)


    def postloop(self):
        if readline:
            readline.set_history_length(histfile_size)
            readline.write_history_file(histfile)


    def do_use(self, args):
        r = re.match(r'(\w+)',args)
        if r:
            self.database = r[1]
            self.prompt = f"TdQuery({self.database})> "
            self.old_prompt = self.prompt
        print(f"current database is {self.database}",file = self.stdout)


    def help_use(self):
        print("change current database", file = self.stdout)
        print("usage: use <database>", file = self.stdout)


    def do_display(self, args):
        if args == 'none':
            self.display_mode = None
        if args in ['horizontal','vertical','csv']:
            self.display_mode = args
        else:
            print("unknown mode. Use horizontal or vertical or none")
        print(f"current display mode is {self.display_mode}")


    def help_display(self):
        print("Change display mode. Usage: display [horizontal|vertical|none]", file = self.stdout)

    def do_quit(self, line):
        return True


    def help_quit(self):
        print("quit the program", file = self.stdout)


    def do_EOF(self,line):
        return True


    def emptyline(self):
        pass


    def execute_query(self, cmds):
        with tdclient.Client(apikey=self.apikey,endpoint=self.endpoint) as client:
            for cmd in cmds:
                # print(f"query = {cmd}", file = self.stdout)

                mode = 'horizontal'
                if self.display_mode:
                    mode = self.display_mode
                else:
                    if cmd[-1] == 'G':
                        mode = 'vertical'

                query_str = cmd.rstrip("\\G;").lstrip()
                # print(f"query_str = {query_str}", file = self.stdout)
                if query_str == '':
                    continue

                print(f"query = {query_str}")
                job = client.query(self.database, query_str, type="presto")
                # sleep until job's finish
                job.wait()
                if not job.result_schema:
                    print("Unknown query or query error", file=self.stdout)
                else:
                    result = PrettyTable(list(map(lambda x : x[0],job.result_schema)))
                    result.align = "l"
                    row_num = 0
                    for row in job.result():
                        result.add_row(row)
                        row_num += 1

                    self.print_table(result,mode)

                    print(f"({row_num} row{'s'[:row_num^1]})")

            self.buffer = ''


    def print_table(self,table,mode = None):
        '''Given a PrettyTable table instance, format each row vertically (similar to mysql's \G display)
            mode: overwrite model display mode if define
        '''
        _mode = mode or self.display_mode
        if ARGS.output_format:
            _mode = 'csv'

        if _mode == 'horizontal':
            print(table,file=self.output)

        if _mode == 'vertical':
            formatted = []
            max_field_width = max([len(x) for x in table._field_names])
            for row_i, row in enumerate(table._rows):
                formatted.append('*************************** %i. row ***************************' % (row_i + 1, ))
                for i, field in enumerate(table._field_names):
                    formatted.append("%s: %s" % (field.rjust(max_field_width), row[i]))
            print('\n'.join(formatted),file=self.output)

        if _mode == 'csv':
            if ARGS.output_format == "CSV":
                writer = csv.writer(self.output,quoting=csv.QUOTE_ALL)
                for row in table._rows:
                    writer.writerow(row)
            if ARGS.output_format == "CSV_HEADER":
                writer = csv.writer(self.output,quoting=csv.QUOTE_ALL)
                writer.writerow(table._field_names)
                for row in table._rows:
                    writer.writerow(row)
            if ARGS.output_format == "CSV_UNQUOTED":
                writer = csv.writer(self.output,quoting=csv.QUOTE_NONE)
                for row in table._rows:
                    writer.writerow(row)
            if ARGS.output_format == "CSV_HEADER_UNQUOTED":
                writer = csv.writer(self.output,quoting=csv.QUOTE_NONE)
                writer.writerow(table._field_names)
                for row in table._rows:
                    writer.writerow(row)

def main():
    global ARGS

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

    # check argument
    if ARGS.output_format and ARGS.output_format not in ['CSV','CSV_HEADER','CSV_UNQUOTED','CSV_HEADER_UNQUOTED']:
        parser.error("output-format got wrong value. Should be one of CSV,CSV_HEADER,CSV_UNQUOTED,CSV_HEADER_UNQUOTED")

    # shell start from here
    f_in = None
    f_out = sys.stdout
    if ARGS.file:
        f_in = open(ARGS.file,'r')
    if ARGS.output:
        f_out = open(ARGS.output,'w')

    shell = TdQuery(stdin = f_in, output = f_out)
    if not shell.apikey or not shell.endpoint:
        print("*** unvalid apikey or endpoint")
        exit(1)
    print(f"*** endpoint = {shell.endpoint}")
    print(f"*** apikey(last 3 digits) = ...{shell.apikey[-3:]}")
    shell.cmdloop()


# main
if __name__ == '__main__':
    main()
