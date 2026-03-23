import argparse
import mysql.connector

parser = argparse.ArgumentParser(add_help=True, description="Script used for registering tag into database.")
parser.add_argument("--verbose", "-v", action ="store_true", help="Prints more information. Used for manual testing.")
parser.add_argument("user", help="Mysql user.")
parser.add_argument("password", help="Mysql user password.")
parser.add_argument("name", help="Name of tag.")
parser.add_argument("tag_hash", help="Hashed public key of tag.")
parser.add_argument("-host", default="localhost" ,help="Mysql host ip.")
parser.add_argument("-database", default="tag_tracker", help="Name of database.")

# Parsing arguments
args = parser.parse_args()

verbose = args.verbose 

# Creating database connection
my_database = mysql.connector.connect(
    host=args.host,
    user=args.user,
    password=args.password,
    database=args.database
)

cursor = my_database.cursor()

if verbose:
    print(f"Inserting hash {args.tag_hash} with name {args.name} ...")

sql = "INSERT INTO tags (name, hashed_key) VALUES (%s, %s)"
val = (args.name, args.tag_hash)

try:
    cursor.execute(sql,val)
    my_database.commit()
    if verbose:
        print("Success!")
except mysql.connector.Error as e:
    print(f"Error: {e}")
