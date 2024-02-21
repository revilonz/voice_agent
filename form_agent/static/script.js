let audioBlob = null; // Global variable to store the audio blob
let isFormProcessed = false; // Flag to check if form has been processed
let silenceStart = null; // Timestamp when silence starts
const silenceDelay = 2000; // Delay in milliseconds, adjust as necessary
let silenceTimeout = null; // Reference to the timeout
let formFieldsDetails = [];
let tempFile = [];
let mediaRecorder;
let audioContext = new (window.AudioContext || window.webkitAudioContext)();
let analyser = audioContext.createAnalyser();
let microphone;
let scriptProcessor = audioContext.createScriptProcessor(2048, 1, 1);
let isRecording = false;
let chunks = [];

window.onload = function() {
    document.addEventListener('click', () => {
        if (!isFormProcessed) {
            processForm();
            isFormProcessed = true; // Set the flag to true after processing
        }
    }, { once: true }); // Ensure this only happens once
};

function processForm() {
    console.log("Processing form...");
    const forms = document.getElementsByTagName('form');
    if (forms.length > 0) {
        const form = forms[0];
        const formData = new FormData();
        const formHtml = form.outerHTML;
        formData.append("htmlContent", formHtml);

        let heading = form.previousElementSibling;
        while (heading && !(/^H[1-6]$/i.test(heading.tagName))) {
            heading = heading.previousElementSibling;
        }
        const formHeading = heading ? heading.innerText : "";
        formData.append("formHeading", formHeading);

        console.log("Sending fetch request to /generate-form-summary...");
        fetch('http://127.0.0.1:5000/generate-form-summary', {
            method: 'POST',
            body: formData
        })
        .then(response => {
            console.log("Received response from /generate-form-summary");
            return response.json();
        })
        .then(data => {
            console.log("Received JSON data:", data);
            formFieldsDetails = data.fields;
            console.log("Fields:", data.fields);
            playAudio(data.audioUrl, () => startAssistant(data.text, data.fields));
            console.log("Summary text:", data.text);
        })
        .catch(error => console.error('Error:', error));
        
    } else {
        console.log('No forms found on the page.');
    }
}

function startAssistant(text, fields) {
    console.log("Starting assistant with text:", text, "and fields:", fields);
    const requestBody = JSON.stringify({text: text, fields: fields});
    console.log("requestBody:", requestBody);   
    fetch('http://127.0.0.1:5000/start_assistant', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: requestBody
    })
    .then(response => response.json()) 
    .then(data => {
        console.log("Playing assistant audio from URL:", data.audioUrl);
        console.log("Form fields:", data.formFields);
        console.log("Temp file path:", data.tempFile);        
        playAudio(data.audioUrl, startRecording); 
    })
    .catch(error => console.error('Error:', error));
}

// PLAY AUDIO

function playAudio(audioUrl, callback) {
    console.log("Playing audio from URL:", audioUrl);
    document.getElementById('statusMessage').innerText = "Playing audio...";
    const audio = new Audio(audioUrl);
    audio.onended = () => {
        console.log("Audio playback ended.");
        document.getElementById('statusMessage').innerText = "Audio playback ended.";
        setTimeout(() => document.getElementById('statusMessage').innerText = "", 3000);
        if (typeof callback === "function") {
            callback();
        }
    };
    audio.play().catch(error => console.error("Audio playback error:", error));
}


// RECORD AUDIO

function startRecording() {
    navigator.mediaDevices.getUserMedia({ audio: true, video: false })
        .then(stream => {
            if (audioContext.state === 'suspended') {
                audioContext.resume();
            }
            microphone = audioContext.createMediaStreamSource(stream);
            microphone.connect(analyser);
            analyser.connect(scriptProcessor);
            scriptProcessor.connect(audioContext.destination);
            scriptProcessor.onaudioprocess = processAudioStream;

            mediaRecorder = new MediaRecorder(stream);
            mediaRecorder.ondataavailable = event => {
                if (event.data.size > 0) chunks.push(event.data);
            };
            mediaRecorder.onstop = processRecordedAudio;

        })
        .catch(error => {
            console.error('startRecording: Error accessing media devices:', error);
            document.getElementById('statusMessage').innerText = "startRecording: Error Unable to access media devices.";
        });
}

function processAudioStream(event) {
    let input = event.inputBuffer.getChannelData(0);
    let sum = 0.0;

    for (let i = 0; i < input.length; ++i) {
        sum += input[i] * input[i];
    }
    let volume = Math.sqrt(sum / input.length);

    if (volume < 0.3) {
        if (isRecording && silenceStart === null) {
            silenceStart = Date.now(); 
            silenceTimeout = setTimeout(() => {
                if (Date.now() - silenceStart >= silenceDelay) {
                    stopRecording();
                }
            }, silenceDelay);
        }
    } else {
        silenceStart = null;
        clearTimeout(silenceTimeout);
        if (!isRecording) {
            startMediaRecording();
        }
    }
}

function startMediaRecording() {
    console.log('startMediaRecording: MediaRecorder started');
    chunks = [];
    mediaRecorder.start();
    isRecording = true;
    document.getElementById('statusMessage').innerText = "Recording... Speak now.";
}

function stopRecording() {
    if (mediaRecorder && mediaRecorder.state !== 'inactive') {
        mediaRecorder.stop();
        console.log('stopRecording: MediaRecorder stopped');
        isRecording = false;
        document.getElementById('statusMessage').innerText = "Recording stopped. Processing...";
        setTimeout(() => document.getElementById('statusMessage').innerText = "", 3000);
    }
}

function processRecordedAudio() {
    document.getElementById('statusMessage').innerText = "processRecordedAudio: Processing recording...";
    if (chunks.length) {
        const audioBlob = new Blob(chunks, { 'type': 'audio/webm' });
        sendAudioToServer(audioBlob, formFieldsDetails, tempFile);
        setTimeout(() => document.getElementById('statusMessage').innerText = "", 3000);
    } else {
        document.getElementById('statusMessage').innerText = "processRecordedAudio: No audio detected. Try again.";
    }
}


function startRecording() {
    navigator.mediaDevices.getUserMedia({ audio: true, video: false })
        .then(stream => {
            const mediaRecorder = new MediaRecorder(stream);
            let chunks = [];

            mediaRecorder.ondataavailable = event => {
                if (event.data.size > 0) chunks.push(event.data);
            };

            mediaRecorder.onstop = () => {
                document.getElementById('statusMessage').innerText = "startRecording: Processing recording...";
                setTimeout(() => document.getElementById('statusMessage').innerText = "", 3000);
                if (chunks.length) {
                    const audioBlob = new Blob(chunks, { 'type': 'audio/webm' });
                    sendAudioToServer(audioBlob, formFieldsDetails, tempFile);
                } else {
                    document.getElementById('statusMessage').innerText = "startRecording: No audio detected. Try again.";
                    setTimeout(() => document.getElementById('statusMessage').innerText = "", 3000);
                }
            };

            mediaRecorder.start();
            setTimeout(() => mediaRecorder.stop(), 5000);
        })
        .catch(error => {
            console.error('startRecording: Error accessing media devices:', error);
            document.getElementById('statusMessage').innerText = "startRecording: Error Unable to access media devices.";
            setTimeout(() => document.getElementById('statusMessage').innerText = "", 3000);
        });
}

function updateFormFields(data) {
    // Check if 'data' contains 'form_fields' and it's an array
    if (data && Array.isArray(data.form_fields)) {
        const formFields = data.form_fields;
        
        // Iterate through each form field and update the corresponding input element
        formFields.forEach(field => {
            const inputElement = document.getElementById(field.id);
            if (inputElement) {
                inputElement.value = field.value; // Update the input element's value
            }
        });
    } else {
        console.log("updateFormFields: Provided data is not a valid array of form fields.");
        setTimeout(() => document.getElementById('statusMessage').innerText = "", 3000);
    }
}


function sendAudioToServer(audioBlob, isSubmit, formFields) {
    const formData = new FormData();
    formData.append("audio", audioBlob);
    formFieldsDetails.forEach(field => {
        formData.append(field.name, field.value);
    });
    formData.append("temp_file_path", tempFile);
    console.log("sendAudioToServer: Preparing to send data to server...", formData);

    fetch('http://127.0.0.1:5000/transcribe', {
        method: 'POST',
        body: formData
    })
    .then(response => {
        console.log("sendAudioToServer: Received response from server");
        return response.json(); 
    })
    .then(data => {
        console.log("sendAudioToServer: Processed JSON response:", data);
        if (data.audioUrl) {
            console.log("sendAudioToServer: Audio URL received:", data.audioUrl);
            playAudio(data.audioUrl, () => {
                if (!data.isSubmit) {
                    startRecording();
                } else {
                    const formFields = data.formFields;
                    console.log("sendAudioToServer: Form submission is complete. Updating form fields...", formFields);
                    updateFormFields(formFields);
                }
            });
        } else {
            console.error("sendAudioToServer: No audio URL returned from server.");
        }
    })
    .catch(error => {
        console.error('sendAudioToServer: Error processing audio:', error);
        document.getElementById('statusMessage').innerText = "sendAudioToServer: Error: Unable to process audio.";
    });
}
