from gtts import gTTS

text = "Hello, this is a test"
tts = gTTS(text=text, lang='en')
tts.save("test_output.mp3")
print("Audio file generated successfully.")

