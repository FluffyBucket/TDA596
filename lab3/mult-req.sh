
for i in `seq 1 20`; do
  curl -d 'entry=first'${i} -X 'POST' 'http://10.1.0.1/board' &
done

for i in `seq 1 20`; do
  curl -d 'entry=second'${i} -X 'POST' 'http://10.1.0.2/board' &
done
