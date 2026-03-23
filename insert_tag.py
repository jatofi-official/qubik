import argparse
import json
import sys
import mysql.connector

parser = argparse.ArgumentParser(add_help=True, description="Script used for inserting locations of a single tag into database. Expects data in json format.")
parser.add_argument("--verbose", "-v", action ="store_true", help="Prints more information. Used for manual testing.")
parser.add_argument("user", help="Mysql user.")
parser.add_argument("password", help="Mysql user password.")
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

def insert_entry(entry):
    sql = "INSERT INTO location_data (time, hashed_key, latitude, longitude, accuracy, battery, confidence) VALUES (%s, %s, %s, %s, %s, %s, %s)"
    val = (entry["time"].replace("T"," "), args.tag_hash ,entry["latitude"], entry["longitude"], entry["accuracy"], entry["battery"], entry["confidence"])
    try:
        cursor.execute(sql,val)
        my_database.commit()
    except mysql.connector.IntegrityError:
        print("Error: Tag is not yet registered")
    except mysql.connector.Error as e:
        print(f"Error: {e}")
        

stdin = sys.stdin.read().lstrip()
decoder = json.JSONDecoder()

json_found = []  

if verbose:
    print("Reading input...")
while len(stdin) > 0:
    parsed_json, consumed = decoder.raw_decode(stdin)
    stdin = stdin[consumed:]

    json_found.append(parsed_json)
    stdin = stdin.lstrip()

if verbose:
    print(f"Read {len(json_found)} entries.")
    print("Inserting into database...")

i = 0
# Inserting each json object
for entry in json_found:
    if verbose:
        print(f"Inserting entry {i}")
    insert_entry(entry)
    i+=1