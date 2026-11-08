#!/bin/bash

# Run from the script's own folder so db.txt, keys.txt and the python scripts are found
# no matter where (cron, other directory) this is started from.
cd "$(dirname "$(readlink -f "$0")")" || exit 1

# Override with e.g. DB_FILE=/path/db.txt KEYS_FILE=/path/keys.txt ./fetch_all.sh
DB_FILE="${DB_FILE:-db.txt}"
KEYS_FILE="${KEYS_FILE:-keys.txt}"

{
    read user
    read password
    read host
    read database
} < "$DB_FILE"

other_flags=""
[[ -n "$host" ]] && other_flags="$other_flags -host $host"   #I used AI for these two lines. They work by checking if variable has non-zero length, then it executes the second part after &&
[[ -n "$database" ]] && other_flags="$other_flags -database $database"


# Same trick as in register_all.sh: keys.txt may not end with a newline, in which case
# `read` would skip the last tag. Appending an empty line fixes it. Blank lines are skipped.
while read -u 9 -r arg1 arg2 name; do
    [[ -z "$arg1" ]] && continue
    python3 fetch_tag_locations.py "$arg1" "$arg2" | python3 insert_tag.py "$user" "$password" "$arg1" $other_flags -v
done 9< <(cat "$KEYS_FILE"; echo "")
