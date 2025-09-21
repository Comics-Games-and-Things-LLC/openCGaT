while true
do
  ./manage.py RetrySubmittedCarts
  date +"%H:%M:%S"
  echo "Waiting until $(printf "tomorrow 4:00"  | date -f -)"
  sleep $(( $( printf '%s\nnow\n' "tomorrow 4:00" | date -f - +%s- ) 0 ))

done