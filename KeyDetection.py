import cv2
import numpy as np
from picamera2 import Picamera2
import time
import pygame
import threading
from gtts import gTTS

# Create the text-to-speech audio file
def create_tts_file(text, filename):
    tts = gTTS(text=text, lang='en')
    tts.save(filename)

# Create the alarm audio file
create_tts_file("Please return the keys", "return_keys.mp3")

# Define the color range for the key in HSV
lower_color = np.array([20, 100, 100])  # Lower bound for a goldish color
upper_color = np.array([30, 255, 255])   # Upper bound for a goldish color

# Initialize the camera
picam2 = Picamera2()
picam2.configure("preview")
picam2.start()

# Allow the camera to warm up
time.sleep(2)

def detect_key(frame):
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    mask = cv2.inRange(hsv, lower_color, upper_color)
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    return contours

def draw_boxes(frame, boxes, countdown):
    for (x_start, y_start, box_width, box_height, color, box_text, label_text) in boxes:
        cv2.rectangle(frame, (x_start, y_start), (x_start + box_width, y_start + box_height), color, 2)
        
        # Center the box text
        text_size = cv2.getTextSize(box_text, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 2)[0]
        text_x = x_start + (box_width - text_size[0]) // 2
        text_y = y_start + (box_height + text_size[1]) // 2
        cv2.putText(frame, box_text, (text_x, text_y), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 2)
        
        # Center the label above the box
        label_size = cv2.getTextSize(label_text, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 2)[0]
        label_x = x_start + (box_width - label_size[0]) // 2
        label_y = y_start - 10
        cv2.putText(frame, label_text, (label_x, label_y), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 2)

        # Display the countdown in the center of the box
        countdown_text = f"{countdown}s"
        countdown_size = cv2.getTextSize(countdown_text, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 2)[0]
        countdown_x = x_start + (box_width - countdown_size[0]) // 2
        countdown_y = y_start + (box_height + countdown_size[1]) // 2 + 15  # Adjust position slightly below the center
        cv2.putText(frame, countdown_text, (countdown_x, countdown_y), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 2)

def is_key_in_box(contours, boxes):
    detected_keys = [False] * len(boxes)
    
    for contour in contours:
        x, y, w, h = cv2.boundingRect(contour)
        key_center = (x + w // 2, y + h // 2)
        
        for i, (bx, by, bw, bh, color, box_text, label_text) in enumerate(boxes):
            if bx <= key_center[0] <= bx + bw and by <= key_center[1] <= by + bh:
                detected_keys[i] = True
                break

    return detected_keys

def alarm_if_no_keys(boxes):
    pygame.mixer.init()  # Initialize the mixer
    pygame.mixer.music.load('return_keys.mp3')  # Load the TTS sound
    last_alarm_time = time.time()
    alarm_triggered = False  # Track if the alarm is currently triggered
    
    while True:
        time.sleep(1)
        if all("Not Available" in box[5] for box in boxes):  # Check if all boxes do not have keys
            current_time = time.time()
            if not alarm_triggered and current_time - last_alarm_time >= 5:  # Trigger after 5 seconds
                pygame.mixer.music.play()  # Play alarm sound
                last_alarm_time = current_time  # Update the last alarm time
                alarm_triggered = True
            elif alarm_triggered and current_time - last_alarm_time >= 5:  # Every 5 seconds after the first alarm
                pygame.mixer.music.play()  # Play alarm sound
                last_alarm_time = current_time  # Update the last alarm time
        else:
            alarm_triggered = False  # Reset the alarm trigger if keys are detected

try:
    boxes = []
    alarm_thread = threading.Thread(target=alarm_if_no_keys, args=(boxes,))
    alarm_thread.start()

    countdown = 60  # Initialize countdown
    start_time = time.time()  # Record the start time
    while True:
        elapsed_time = time.time() - start_time  # Calculate elapsed time
        frame = picam2.capture_array()
        contours = detect_key(frame)

        height, width, _ = frame.shape
        box_width = (width // 4) - 10
        box_height = box_width
        boxes = []

        space = 10

        for i in range(4):
            x_start = i * (box_width + space)
            y_start = (height - box_height) // 2
            color = (0, 0, 255)
            box_text = "Keys Not Available"
            label_text = f"Box {i + 1}"
            boxes.append((x_start, y_start, box_width, box_height, color, box_text, label_text))

        detected_keys = is_key_in_box(contours, boxes)

        for i, detected in enumerate(detected_keys):
            boxes[i] = (*boxes[i][:4], (0, 255, 0) if detected else (0, 0, 255), 
                         "Keys Available" if detected else "Keys Not Available", boxes[i][6])

        # Update the alarm thread with current boxes
        alarm_thread.args = (boxes,)
        
        draw_boxes(frame, boxes, countdown)

        # Decrease countdown every second
        if countdown > 0:
            countdown -= 1
        
        if countdown < 0:  # Reset countdown if it reaches below zero
            countdown = 60

        # Stop the alarm if all keys are detected
        if all(detected_keys):
            pygame.mixer.music.stop()  # Stop alarm if all keys are detected

        cv2.imshow("Original Frame", frame)

        if cv2.waitKey(1) & 0xFF == ord('q'):
            break
finally:
    picam2.stop()
    cv2.destroyAllWindows()
