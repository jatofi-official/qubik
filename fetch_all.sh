while read -r arg1 arg2; do
    python3 fetch_tag_locations.py "$arg1" "$arg2"
done < keys.txt
