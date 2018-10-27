import xml.etree.ElementTree as ET
import string
import datetime
import sqlite3
import sys
import logging

from src.html.htmlparser import first_element_with_tag, first_element_with_tag_and_attributes, \
    all_elements_with_tag_and_attributes, strip_time_zone
from src.sql.sqlgenerator import SqlGenerator

MESSAGES_FILE_NAME = sys.argv[1]    # Facebook messages file path. Archive usually "messages.htm".
USER_ALIASES = lines = [line.rstrip('\n') for line in open(sys.argv[2])]    # Reads the alias file, puts into list.
PREFERRED_ALIAS_INDEX = int(sys.argv[3])-1   # Line number in alias file that preferred alias appears on.


def run_query(query_string, con):
    """
    Run a query on a SQLite database.
    :param query_string: Query to run.
    :param con: Connection to run query on.
    :return: Result of query.
    """
    logging.info("Running query: '{}'".format(query_string))
    cur = con.cursor()
    cur.execute(query_string)
    logging.info("Query ran successfully.")
    return cur.fetchall()


def create_database_from_html(location=":memory:"):
    """
    Parses HTML of a facebook message data sump and stores the data in an SQLite database.
    :param location: Location of database - :memory: by default.
    :return: Connection to newly created database.
    """
    with open(MESSAGES_FILE_NAME, "r") as file:
        file_string = file.read()
    filtered_string = filter(lambda x: x in string.printable, file_string)  # Strip non-printable characters

    # Setup memory-based database
    con = sqlite3.connect(location)

    # Define and create messages table
    messages_table_details = {
        "name": "Messages",
        "rows": [
            {
                "name": "Message_ID",
                "type": "integer",
                "attributes": ["primary", "key", "autoincrement"]
            },
            {
                "name": "Message_Text",
                "type": "text"
            },
            {
                "name": "Message_DateTime",
                "type": "text"
            },
            {
                "name": "Message_Sender",
                "type": "text"
            },
            {
                "name": "Message_Receiver",
                "type": "text"
            }
        ]
    }
    run_query(SqlGenerator.get_query_create_table(messages_table_details), con)

    # Form the XML structure
    root = ET.fromstring(filtered_string)

    # Narrow down to just contents
    body = first_element_with_tag(root, "body")
    contents = first_element_with_tag_and_attributes(body, "div", "class", "contents")

    for block in contents:
        if block.tag == "div":  # All threads are held in some empty container div
            threads = all_elements_with_tag_and_attributes(block, "div", "class",
                                                           "thread")  # All the threads in this div
            for thread in threads:

                # Establish the friend name
                thread_names = [x.strip() for x in thread.text.split(",")]
                thread_names_without_user = [x for x in thread_names if x not in USER_ALIASES]
                if len(thread_names_without_user) != 1:
                    continue  # Group chats not supported
                title = thread_names_without_user[0]

                # Read as header/body pairs
                for i in range(0, len(thread), 2):
                    header = first_element_with_tag_and_attributes(thread[i], "div", "class", "message_header")

                    message_sender = first_element_with_tag_and_attributes(header, "span", "class", "user").text
                    if message_sender in USER_ALIASES:
                        message_sender = USER_ALIASES[PREFERRED_ALIAS_INDEX]
                        message_receiver = title
                    else:
                        message_receiver = USER_ALIASES[PREFERRED_ALIAS_INDEX]

                    message_time_raw_string = first_element_with_tag_and_attributes(header, "span", "class",
                                                                                    "meta").text
                    normalised_time_string = strip_time_zone(message_time_raw_string)
                    message_time = datetime.datetime.strptime(normalised_time_string, "%A, %d %B %Y at %H:%M")

                    message_body = thread[i + 1].text

                    # No support for strings with ' currently. To be fixed in later versions.
                    if message_body is not None:
                        message_body = message_body.replace("'", "")
                    if message_sender is not None:
                        message_sender = message_sender.replace("'", "")
                    if message_receiver is not None:
                        message_receiver = message_receiver.replace("'", "")

                    insertion_values = {
                        "Message_Text": message_body,
                        "Message_DateTime": message_time,
                        "Message_Sender": message_sender,
                        "Message_Receiver": message_receiver,
                    }

                    insertion_query = SqlGenerator.get_query_insert_into_table(messages_table_details, insertion_values)
                    try:
                        run_query(insertion_query, con)
                    except sqlite3.OperationalError:
                        logging.error("Query failed.")
                        continue
                    logging.debug("Sender: " + str(message_sender) + ", Time: " + str(message_time) + ", Message: "
                                  + str(message_body))
    return con


if __name__ == '__main__':
    database_connection = create_database_from_html()

    # Example query. Output all messages to and from user account in order of sending.
    all_messages_sorted_query = run_query(
        "SELECT Message_Sender, Message_DateTime, Message_Text FROM Messages ORDER BY datetime(Message_DateTime)",
        database_connection)
    with open("query_output.txt", "w") as output_file:
        for message in all_messages_sorted_query:
            output_file.write(str(message[0]) + "\n" + str(message[1]) + "\n" + str(message[2]) + "\n\n")