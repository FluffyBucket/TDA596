#Post to messages to the board
echo "Adding two entries:"
curl -d 'entry=first' -X 'POST' 10.1.0.1/board
curl -d 'entry=second' -X 'POST' 10.1.0.1/board
sleep 10
#Modifies a value
echo "Editing id:0"
curl -d 'entry=first_edited&delete=0' -X 'POST' 10.1.0.1/board/0

#Deletes a value
echo "Delete id:1"
curl -d 'entry=second&delete=1' -X 'POST' 10.1.0.1/board/1

sleep 5
#Hopefully shows the consistenty issues
curl -d 'entry=I was sent to #1' -X 'POST' 10.1.0.1/board & curl -d 'entry=I was sent to #2' -X 'POST' 10.1.0.2/board &
