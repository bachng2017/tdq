""" util
"""

import sqlparse

SQL_DELIMITER = '\G'
PLACE_HOLDER = "\ufffc"

def split_sql(stm):
    result = []
    tmp_lst = sqlparse.split(stm)

    for tmp in tmp_lst:
        t = sqlparse.split(tmp.replace(';',PLACE_HOLDER).replace(SQL_DELIMITER,';'))
        result += [s.replace(';',SQL_DELIMITER).replace(PLACE_HOLDER,';') for s in t]

    return result

