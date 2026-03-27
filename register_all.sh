#!/bin/bash

{
    read user
    read password
    read host
    read database
} < db.txt

other_flags=""
[[ -n "$host" ]] && other_flags="$other_flags -host $host"
[[ -n "$database" ]] && other_flags="$other_flags -database $database"

# I used AI to help me with the custom input
# It creates a custom output pipe which has the content of keys.txt, 
# in addition the file always ends with an endline, otherwise the last line was not read.
while read -u 9 -r arg1 arg2 name; do
    python3 register_tag.py "$user" "$password" "$name" "$arg1" $other_flags
done 9< <(cat keys.txt; echo "")
