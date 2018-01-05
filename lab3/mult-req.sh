for id in `seq 1 8`; do
    for i in `seq 1 40`; do
      curl -d 'entry=node:'${id}'_msg:'${i} -X 'POST' 'http://10.1.0.'${id}'/board' &
    done
done
