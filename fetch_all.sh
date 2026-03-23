#!/bin/bash

{
    read user
    read password
    read host
    read database
} < db.txt

other_flags = ""
[[ -n "$host" ]] && other_flags="$other_flags -host $host"   #I used AI for these two lines. They work by checking if variable has non-zero length, then it executes the second part after &&
[[ -n "$database" ]] && other_flags="$other_flags -database $database"


while read -r arg1 arg2; do
    python3 fetch_tag_locations.py "$arg1" "$arg2" | python3 insert_tag.py "$user" "$password" "$arg1" $other_flags
done < keys.txt
