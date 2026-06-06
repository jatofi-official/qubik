import mysql.connector
import argparse
import sqlite3
import sys

parser = argparse.ArgumentParser(add_help=True, description="Script used for inserting locations of a single tag into database. Expects data in json format.")
parser.add_argument("--verbose", "-v", action ="store_true", help="Prints more information. Used for manual testing.")
parser.add_argument("user", help="Mysql user.")
parser.add_argument("password", help="Mysql user password.")
parser.add_argument("-host", default="localhost" ,help="Mysql host ip.")
parser.add_argument("-database", default="tag_tracker", help="Name of mysql database.")
parser.add_argument("-sqlite", default="../largeDB.db", help="Name of sqlite .db file.")



# Parsing arguments
args = parser.parse_args()

verbose = args.verbose 


my_database = mysql.connector.connect(
    host=args.host,
    user=args.user,
    password=args.password,
    database=args.database
)

sqlite_connection = sqlite3.connect(args.sqlite)
sqlite_cursor = sqlite_connection.cursor()


def import_tags():
    if verbose:
        print("Getting tags from mysql database...")
    get_sql = "SELECT * FROM tags"
    mysql_cursor.execute(get_sql)
    tags = mysql_cursor.fetchall()

    if verbose:
        print("Importing tags to sqlite database...")

    for tag in tags:
        import_sql = "INSERT INTO tags (id, name, hashed_key) VALUES (?, ?, ?)"
        sqlite_cursor.execute(import_sql, tag)
        sqlite_connection.commit()

def import_location_data():
    if verbose:
        print("Getting location_data from mysql database...")
    get_sql = "SELECT * FROM location_data"
    mysql_cursor.execute(get_sql)
    location_data = mysql_cursor.fetchall()

    if verbose:
        print("Importing location_data to sqlite database...")

    if verbose:
        i = 1
    for row in location_data:
        import_sql = "INSERT INTO location_data (id, time, hashed_key, latitude, longitude, accuracy, confidence) VALUES (?, ?, ?, ?, ?, ?, ?)"
        
        updated_time = row[1].strftime("%Y-%m-%d %H:%M:%S")

        if verbose:
            sys.stdout.write("Progress: %d / %d \r" % (i, len(location_data))) # Although getting this handy code from stackoverflow, I had some error and asked AI for help fixing it
            if(i != len(location_data)):
                sys.stdout.flush()
            else:
                sys.stdout.write("\n")
                sys.stdout.flush()  


        sqlite_cursor.execute(import_sql, [row[0], updated_time, row[2], row[3], row[4], row[5], row[7]])
        i += 1
    
    sqlite_connection.commit()

    if verbose:
        print("Done!")


mysql_cursor = my_database.cursor()

import_tags()
import_location_data()