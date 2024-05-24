from flask import Flask, request, jsonify, send_file
import os
import cv2
import json
import re
import numpy as np
from urllib.parse import urlparse, parse_qs
from pytube import YouTube, exceptions
from flask_cors import CORS
import shutil
import threading
app = Flask(__name__)
CORS(app)

def fetch_video(text_input):
    with open('MS-ASL/MSASL_test.json', 'r') as f:
        data = json.load(f)

    video_paths = []
    start_times = []
    end_times = []

    for word in text_input.split():
        found_video = False
        for item in data:
            if item['clean_text'] == word:
                video_url = item['url']
                print(f"Video URL for '{word}': {video_url}")
                try:
                    youtube = YouTube(video_url)
                    video = youtube.streams.first()
                    video_path = video.download()
                    start_time = item['start_time']
                    end_time = item['end_time']
                    video_paths.append(video_path)
                    start_times.append(start_time)
                    end_times.append(end_time)
                    found_video = True
                    break
                except exceptions.VideoUnavailable:
                    print(f"Video for '{word}' is unavailable.")

        if not found_video:
            print(f"No video found for the word '{word}'.")

    return video_paths, start_times, end_times

def merge_videos(video_paths, start_times, end_times):
    output_video_path = "output.mp4"
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    frame_width = int(cv2.VideoCapture(video_paths[0]).get(cv2.CAP_PROP_FRAME_WIDTH))
    frame_height = int(cv2.VideoCapture(video_paths[0]).get(cv2.CAP_PROP_FRAME_HEIGHT))
    output_video = cv2.VideoWriter(output_video_path, fourcc, 25, (frame_width, frame_height))

    for i, video_path in enumerate(video_paths):
        cap = cv2.VideoCapture(video_path)

        if not cap.isOpened():
            print(f'Error opening video file for word {i + 1}')
            continue

        cap.set(cv2.CAP_PROP_POS_MSEC, start_times[i] * 1000)

        while True:
            ret, frame = cap.read()

            if not ret:
                break

            current_time = cap.get(cv2.CAP_PROP_POS_MSEC) / 1000
            if start_times[i] <= current_time <= end_times[i]:
                output_video.write(frame)

            if current_time >= end_times[i]:
                break

        cap.release()

    output_video.release()
    return output_video_path


@app.route('/fetch_asl_video', methods=['POST'])
def fetch_asl_video():
    text_input = request.json['text']
    video_paths, start_times, end_times = fetch_video(text_input)

    if video_paths:
        # Merge videos and return the output video file as a response
        output_video_path = merge_videos(video_paths, start_times, end_times)
        if os.path.exists(output_video_path):
            # Start a new thread to run the cleanup function
            threading.Thread(target=cleanup, args=(output_video_path, video_paths)).start()

            response = send_file(output_video_path, mimetype='video/mp4')
            return response
        else:
            return jsonify({'success': False, 'error': 'Failed to generate output video.'})
    else:
        return jsonify({'success': False, 'error': 'No videos found for the given text input.'})


def cleanup(output_video_path, video_paths):
    # Wait for a short delay to allow the response to be sent
    threading.Event().wait(timeout=5)

    # Remove output_video_path file
    if os.path.exists(output_video_path):
        os.remove(output_video_path)

    # Remove files in video_paths
    for path in video_paths:
        if os.path.isfile(path):
            os.remove(path)
        elif os.path.isdir(path):
            shutil.onexc(path, ignore_errors=True, onerror=None)


if __name__ == '__main__':
    app.run(debug=True, host="0.0.0.0", port=5000)