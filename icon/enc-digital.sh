#!/usr/bin/env bash

st=13.56
ed=3.3

IFS=$'\n'
[[ -d ../encode ]] || mkdir '../encode'
for i in $(ls -1 *.mp4); do
    duration=$(ffmpeg -i "$i" 2>&1 | grep 'Duration' | cut -d ' ' -f 4 | sed 's/,//g')
    ttt_1=$(/home/rachpt/time-subtracrtion.sh $duration $st)
    tt=$(/home/rachpt/time-subtracrtion.sh $ttt_1 $ed)
    echo "$i"
    ffmpeg -ss $st -i "$i" -t "$tt" -r 30 -c:v libx264 -preset fast -filter_complex \
        "[0:v]setpts=10/16 *PTS[v];[0:a]atempo=1.6[a]" -map "[v]" -map "[a]" \
        -metadata comment="made by rach" "../encode/$i" -y 2>/dev/null
done
