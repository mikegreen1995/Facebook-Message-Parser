import logging


def run_query(query_string, con):
    """
    Run a query on a SQLite database.
    :param query_string: Query to run.
    :param con: Connection to run query on.
    :return: Result of query.
    """
    logging.debug("Running query: '{}'".format(query_string))
    cur = con.cursor()
    cur.execute(query_string)
    logging.debug("Query ran successfully.")
    return cur.fetchall()