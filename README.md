![Downloads](https://static.pepy.tech/badge/tdq)


# tdq
Treasure Data Query shell 

## Install
```
pip install tdq
```

## Features
A wrapper for td-client that focus on SQL query with following feature
- bash-like history-list editing (e.g. Control-P scrolls back to the last command, Control-N forward to the next one, Control-F moves the cursor to the right non-destructively, Control-B moves the cursor to the left non-destructively, etc.).
- directly execute SQL to the remote TD endpoint
- support multi-line queries
- support horizontal, vertical and CSV format ouput

## Usage
Start the shell with default configuration
```
tdq
```

See all the command parameters:
```
tdq --help
```

Run the shell with predefined sql queries and write the result ot a CSV file
```
tdq -f input.sql -o output.csv --output-format CSV_HEADER
```

Besides valid commands, all user's inputs are considered SQL queries.

Currently, below commands are supported:
- help: display valid commands
- use <database> : change current database. This could be set by -d option or read from default TD client config file
- display <mode>: change current display mode. Value is among `horizontal`,`vertical` or `None`(auto)
- quit: quit the shell (same with Ctrl-D)

Use `-h` to see all options


## Configuration
tdq will utilize the file ~/.td/td.conf created by td-client for default configuration

For example, a typical td.conf looks like below:
```td.conf
[account]
  apikey = <apikey>
  endpoint = https://api.treasuredata.co.jp/
  database = <default database>
```

Alternately, apikey and endpoint could be defined by environmental variables `TD_API_KEY` and `TD_SERVER`
Endpoint also could be define by `-e` option.



## Other
- see [here](https://github.com/treasure-data/td-client-python) for details about Treasure Data Python client
