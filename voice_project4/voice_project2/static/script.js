// Get all elements
let speakNow = document.getElementById('speakNow');
let recordedAudio = document.getElementById('recordedAudio');
let fileInput = document.getElementById('fileInput');
let fileAudio = document.getElementById('fileAudio');
let submitBtn = document.getElementById('submitBtn');
let generatedAudio = document.getElementById('generatedAudio');
let textBox = document.getElementById('textBox');

let mediaRecorder;
let audioChunks = [];

// 🎤 Start Recording Audio
speakNow.addEventListener('click', function () {
    navigator.mediaDevices.getUserMedia({ audio: true })
        .then(stream => {
            mediaRecorder = new MediaRecorder(stream);
            audioChunks = [];

            mediaRecorder.ondataavailable = event => {
                audioChunks.push(event.data);
            };

            mediaRecorder.onstop = () => {
                let audioBlob = new Blob(audioChunks, { type: 'audio/mp3' });
                let audioUrl = URL.createObjectURL(audioBlob);
                recordedAudio.src = audioUrl;
                recordedAudio.style.display = "block";
                convertAudioToText(audioBlob);
            };

            mediaRecorder.start();
            speakNow.textContent = "🛑 Stop Recording";
            speakNow.onclick = stopRecording;
        })
        .catch(error => alert("Microphone access denied!"));
});

// 🛑 Stop Recording
function stopRecording() {
    mediaRecorder.stop();
    speakNow.textContent = "🎤 Start Recording";
    speakNow.onclick = startRecording;
}

// 📂 Handle File Upload & Show Audio Preview
fileInput.addEventListener('change', function (event) {
    let file = event.target.files[0];
    if (file) {
        let fileUrl = URL.createObjectURL(file);
        fileAudio.src = fileUrl;
        fileAudio.style.display = "block";
        submitBtn.style.display = "block";  // Show Submit Button
    }
});

// ✔ Process Uploaded Audio
submitBtn.addEventListener('click', function () {
    let file = fileInput.files[0];
    if (file) {
        convertAudioToText(file);
    }
});

// 🎙 Convert Audio to Text (Speech Recognition)
function convertAudioToText(audioBlob) {
    let recognition = new (window.SpeechRecognition || window.webkitSpeechRecognition)();
    recognition.lang = 'en-US';
    recognition.interimResults = false;
    recognition.maxAlternatives = 1;

    let reader = new FileReader();
    reader.readAsDataURL(audioBlob);
    reader.onloadend = function () {
        recognition.onresult = function (event) {
            let transcript = event.results[0][0].transcript;
            textBox.textContent = transcript;
            textBox.style.display = "block";
            generateAudio(transcript);
        };
    };

    recognition.onerror = function () {
        textBox.textContent = "Could not convert audio to text.";
        textBox.style.display = "block";
    };

    recognition.start();
}

// 🔊 Generate Audio from Text (Text-to-Speech)
function generateAudio(text) {
    let speech = new SpeechSynthesisUtterance();
    speech.text = text;
    speech.lang = "en-US";
    speech.rate = 1;
    speech.pitch = 1;

    let synth = window.speechSynthesis;
    synth.speak(speech);

    let audioUrl = URL.createObjectURL(new Blob([text], { type: 'audio/mp3' }));
    generatedAudio.src = audioUrl;
    generatedAudio.style.display = "block";
}
